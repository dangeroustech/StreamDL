package main

import (
	"bytes"
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	log "github.com/sirupsen/logrus"
)

// DownloadKind identifies whether a download is a live stream or a VOD.
type DownloadKind string

const (
	DownloadKindLive DownloadKind = "live"
	DownloadKindVOD  DownloadKind = "vod"
)

// DownloadProgress is a point-in-time snapshot of an active FFmpeg download.
type DownloadProgress struct {
	Key             string
	Channel         string
	Kind            DownloadKind
	VodID           string
	Title           string
	SizeBytes       int64
	Duration        time.Duration
	TotalDuration   time.Duration // known for some VODs; 0 if unknown
	Speed           float64       // realtime multiplier; 0 if unknown / N/A
	BitrateKbps     float64
	Percent         *float64
	ETA             *time.Duration
	StartedAt       time.Time
	UpdatedAt       time.Time
}

// ProgressMeta describes a download when it is registered.
type ProgressMeta struct {
	Channel       string
	Kind          DownloadKind
	VodID         string
	Title         string
	TotalDuration time.Duration
}

type progressStore struct {
	mu    sync.RWMutex
	items map[string]*DownloadProgress
}

func newProgressStore() *progressStore {
	return &progressStore{items: make(map[string]*DownloadProgress)}
}

// downloadProgress is the process-wide active-download registry; tests may replace it.
var downloadProgress = newProgressStore()

func progressKeyLive(channel string) string {
	return "live:" + channel
}

func progressKeyVOD(channel, vodID string) string {
	return "vod:" + channel + ":" + vodID
}

// Start registers (or resets) an active download entry.
func (s *progressStore) Start(key string, meta ProgressMeta) {
	now := time.Now()
	s.mu.Lock()
	defer s.mu.Unlock()
	s.items[key] = &DownloadProgress{
		Key:           key,
		Channel:       meta.Channel,
		Kind:          meta.Kind,
		VodID:         meta.VodID,
		Title:         meta.Title,
		TotalDuration: meta.TotalDuration,
		StartedAt:     now,
		UpdatedAt:     now,
	}
}

// End removes an active download entry.
func (s *progressStore) End(key string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.items, key)
}

// Update applies a parsed FFmpeg progress sample to an active download.
func (s *progressStore) Update(key string, sample ffmpegProgressSample) {
	s.mu.Lock()
	defer s.mu.Unlock()
	p, ok := s.items[key]
	if !ok {
		return
	}
	if sample.SizeBytes > 0 {
		p.SizeBytes = sample.SizeBytes
	}
	if sample.Duration > 0 {
		p.Duration = sample.Duration
	}
	if sample.Speed > 0 {
		p.Speed = sample.Speed
	}
	if sample.BitrateKbps > 0 {
		p.BitrateKbps = sample.BitrateKbps
	}
	p.UpdatedAt = time.Now()
	p.Percent, p.ETA = derivePercentETA(p.Duration, p.TotalDuration, p.Speed)
}

// Get returns a copy of one download's progress, if present.
func (s *progressStore) Get(key string) (DownloadProgress, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	p, ok := s.items[key]
	if !ok {
		return DownloadProgress{}, false
	}
	return *p, true
}

// Snapshot returns a stable, sorted copy of all active downloads.
func (s *progressStore) Snapshot() []DownloadProgress {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]DownloadProgress, 0, len(s.items))
	for _, p := range s.items {
		out = append(out, *p)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Channel != out[j].Channel {
			return out[i].Channel < out[j].Channel
		}
		if out[i].Kind != out[j].Kind {
			return out[i].Kind < out[j].Kind
		}
		return out[i].VodID < out[j].VodID
	})
	return out
}

func derivePercentETA(elapsed, total time.Duration, speed float64) (*float64, *time.Duration) {
	if total <= 0 || elapsed <= 0 {
		return nil, nil
	}
	pct := (float64(elapsed) / float64(total)) * 100
	if pct < 0 {
		pct = 0
	}
	if pct > 100 {
		pct = 100
	}
	percent := pct

	var eta *time.Duration
	if speed > 0 && elapsed < total {
		remaining := time.Duration(float64(total-elapsed) / speed)
		eta = &remaining
	}
	return &percent, eta
}

// ffmpegProgressSample is one parsed progress update from FFmpeg output.
type ffmpegProgressSample struct {
	SizeBytes   int64
	Duration    time.Duration
	Speed       float64
	BitrateKbps float64
	Valid       bool
}

var (
	reSize    = regexp.MustCompile(`(?:^|\s)size=\s*([0-9.]+)\s*([KkMmGg]?i?[Bb])`)
	reTime    = regexp.MustCompile(`(?:^|\s)time=\s*(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)`)
	reSpeed   = regexp.MustCompile(`(?:^|\s)speed=\s*([0-9.]+)x`)
	reBitrate = regexp.MustCompile(`(?:^|\s)bitrate=\s*([0-9.]+)kbits/s`)
	// -progress key=value form
	reKV = regexp.MustCompile(`^([a-zA-Z0-9_]+)=(.+)$`)
)

// parseFFmpegProgressLine extracts progress fields from a single FFmpeg status line
// or a -progress key=value line. Returns Valid=false when the line is not progress.
func parseFFmpegProgressLine(line string) ffmpegProgressSample {
	line = strings.TrimSpace(line)
	if line == "" {
		return ffmpegProgressSample{}
	}

	// -progress machine-readable lines
	if m := reKV.FindStringSubmatch(line); m != nil && !strings.Contains(line, " ") {
		sample := ffmpegProgressSample{}
		switch m[1] {
		case "total_size":
			if n, err := strconv.ParseInt(strings.TrimSpace(m[2]), 10, 64); err == nil && n > 0 {
				sample.SizeBytes = n
				sample.Valid = true
			}
		case "out_time_ms":
			// FFmpeg out_time_ms is actually microseconds despite the name.
			if n, err := strconv.ParseInt(strings.TrimSpace(m[2]), 10, 64); err == nil && n > 0 {
				sample.Duration = time.Duration(n) * time.Microsecond
				sample.Valid = true
			}
		case "out_time_us":
			if n, err := strconv.ParseInt(strings.TrimSpace(m[2]), 10, 64); err == nil && n > 0 {
				sample.Duration = time.Duration(n) * time.Microsecond
				sample.Valid = true
			}
		case "out_time":
			if d, ok := parseFFmpegClock(strings.TrimSpace(m[2])); ok {
				sample.Duration = d
				sample.Valid = true
			}
		case "speed":
			val := strings.TrimSuffix(strings.TrimSpace(m[2]), "x")
			if n, err := strconv.ParseFloat(val, 64); err == nil && n > 0 {
				sample.Speed = n
				sample.Valid = true
			}
		case "bitrate":
			val := strings.TrimSpace(m[2])
			val = strings.TrimSuffix(val, "kbits/s")
			if n, err := strconv.ParseFloat(val, 64); err == nil && n > 0 {
				sample.BitrateKbps = n
				sample.Valid = true
			}
		}
		return sample
	}

	// Human status line: frame=... size=... time=... bitrate=... speed=...
	if !strings.Contains(line, "size=") && !strings.Contains(line, "time=") && !strings.Contains(line, "speed=") {
		return ffmpegProgressSample{}
	}

	sample := ffmpegProgressSample{}
	if m := reSize.FindStringSubmatch(line); m != nil {
		if n, err := parseFFmpegSize(m[1], m[2]); err == nil {
			sample.SizeBytes = n
			sample.Valid = true
		}
	}
	if m := reTime.FindStringSubmatch(line); m != nil {
		hours, _ := strconv.Atoi(m[1])
		mins, _ := strconv.Atoi(m[2])
		secs, _ := strconv.ParseFloat(m[3], 64)
		sample.Duration = time.Duration(hours)*time.Hour +
			time.Duration(mins)*time.Minute +
			time.Duration(secs*float64(time.Second))
		sample.Valid = true
	}
	if m := reSpeed.FindStringSubmatch(line); m != nil {
		if n, err := strconv.ParseFloat(m[1], 64); err == nil {
			sample.Speed = n
			sample.Valid = true
		}
	}
	if m := reBitrate.FindStringSubmatch(line); m != nil {
		if n, err := strconv.ParseFloat(m[1], 64); err == nil {
			sample.BitrateKbps = n
			sample.Valid = true
		}
	}
	return sample
}

func parseFFmpegClock(v string) (time.Duration, bool) {
	if v == "" || strings.EqualFold(v, "N/A") {
		return 0, false
	}
	parts := strings.Split(v, ":")
	if len(parts) != 3 {
		return 0, false
	}
	hours, errH := strconv.Atoi(parts[0])
	mins, errM := strconv.Atoi(parts[1])
	secs, errS := strconv.ParseFloat(parts[2], 64)
	if errH != nil || errM != nil || errS != nil {
		return 0, false
	}
	return time.Duration(hours)*time.Hour +
		time.Duration(mins)*time.Minute +
		time.Duration(secs*float64(time.Second)), true
}

func parseFFmpegSize(value, unit string) (int64, error) {
	n, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return 0, err
	}
	mult := 1.0
	switch strings.ToLower(unit) {
	case "b":
		mult = 1
	case "kb", "kib":
		mult = 1024
	case "mb", "mib":
		mult = 1024 * 1024
	case "gb", "gib":
		mult = 1024 * 1024 * 1024
	default:
		return 0, fmt.Errorf("unknown size unit %q", unit)
	}
	return int64(n * mult), nil
}

// ffmpegLogWriter tees FFmpeg stderr into a tail buffer while parsing progress lines.
type ffmpegLogWriter struct {
	key           string
	store         *progressStore
	mu            sync.Mutex
	buf           bytes.Buffer
	partial       []byte
	maxBytes      int
	lastDebugAt   time.Time
	debugInterval time.Duration
}

func newFFmpegLogWriter(key string, store *progressStore) *ffmpegLogWriter {
	return &ffmpegLogWriter{
		key:           key,
		store:         store,
		maxBytes:      64 * 1024,
		debugInterval: 10 * time.Second,
	}
}

func (w *ffmpegLogWriter) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()

	if _, err := w.buf.Write(p); err != nil {
		return 0, err
	}
	if w.buf.Len() > w.maxBytes {
		trimmed := w.buf.Bytes()[w.buf.Len()-w.maxBytes:]
		w.buf.Reset()
		w.buf.Write(trimmed)
	}

	data := append(w.partial, p...)
	w.partial = w.partial[:0]

	start := 0
	for i := 0; i < len(data); i++ {
		if data[i] == '\n' || data[i] == '\r' {
			if i > start {
				w.handleLine(string(data[start:i]))
			}
			start = i + 1
		}
	}
	if start < len(data) {
		w.partial = append(w.partial[:0], data[start:]...)
	}
	return len(p), nil
}

func (w *ffmpegLogWriter) handleLine(line string) {
	sample := parseFFmpegProgressLine(line)
	if !sample.Valid {
		return
	}
	w.store.Update(w.key, sample)

	now := time.Now()
	if !w.lastDebugAt.IsZero() && now.Sub(w.lastDebugAt) < w.debugInterval {
		return
	}
	w.lastDebugAt = now
	if p, ok := w.store.Get(w.key); ok {
		log.Debugf("download progress %s", formatDownloadProgress(p))
	}
}

// String returns the accumulated log buffer (for failure tails).
func (w *ffmpegLogWriter) String() string {
	w.mu.Lock()
	defer w.mu.Unlock()
	return w.buf.String()
}

func formatDownloadProgress(p DownloadProgress) string {
	var b strings.Builder
	fmt.Fprintf(&b, "[%s] %s", p.Channel, p.Kind)
	if p.Kind == DownloadKindVOD {
		label := p.Title
		if label == "" {
			label = p.VodID
		}
		if label != "" {
			fmt.Fprintf(&b, " %q", label)
		}
	}
	if p.Percent != nil {
		fmt.Fprintf(&b, " %.1f%%", *p.Percent)
	}
	if p.SizeBytes > 0 {
		fmt.Fprintf(&b, " size=%s", formatBytes(p.SizeBytes))
	}
	if p.Duration > 0 {
		fmt.Fprintf(&b, " time=%s", formatDurationShort(p.Duration))
	}
	if p.Speed > 0 {
		fmt.Fprintf(&b, " speed=%.2fx", p.Speed)
	}
	if p.ETA != nil {
		fmt.Fprintf(&b, " eta=%s", formatDurationShort(*p.ETA))
	}
	return b.String()
}

func formatBytes(n int64) string {
	const (
		kib = 1024
		mib = 1024 * kib
		gib = 1024 * mib
	)
	switch {
	case n >= gib:
		return fmt.Sprintf("%.2fGiB", float64(n)/float64(gib))
	case n >= mib:
		return fmt.Sprintf("%.1fMiB", float64(n)/float64(mib))
	case n >= kib:
		return fmt.Sprintf("%.1fKiB", float64(n)/float64(kib))
	default:
		return fmt.Sprintf("%dB", n)
	}
}

func formatDurationShort(d time.Duration) string {
	if d < 0 {
		d = 0
	}
	d = d.Round(time.Second)
	h := int(d.Hours())
	m := int(d.Minutes()) % 60
	s := int(d.Seconds()) % 60
	if h > 0 {
		return fmt.Sprintf("%dh%02dm%02ds", h, m, s)
	}
	if m > 0 {
		return fmt.Sprintf("%dm%02ds", m, s)
	}
	return fmt.Sprintf("%ds", s)
}

// logActiveDownloadSummary writes an INFO summary of in-flight downloads for the
// tick into the primary log sink, and mirrors a plain Active Downloads block to
// stdout when logging is file-primary (see setupLogging).
func logActiveDownloadSummary(store *progressStore) {
	snap := store.Snapshot()
	if len(snap) == 0 {
		log.Debug("Active Downloads: (none)")
	} else {
		log.Info("Active Downloads:")
		for _, p := range snap {
			log.Infof("  %s", formatDownloadProgress(p))
		}
	}
	writeConsoleDownloadSummary(store)
}
