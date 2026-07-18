package main

import (
	"strings"
	"testing"
	"time"
)

func TestParseFFmpegProgressLine_StatusLine(t *testing.T) {
	line := "frame= 1234 fps= 30 q=28.0 size=    1024kB time=00:00:41.20 bitrate= 203.4kbits/s speed=1.01x"
	sample := parseFFmpegProgressLine(line)
	if !sample.Valid {
		t.Fatal("expected valid sample")
	}
	if sample.SizeBytes != 1024*1024 {
		t.Fatalf("size=%d want %d", sample.SizeBytes, 1024*1024)
	}
	wantDur := 41*time.Second + 200*time.Millisecond
	if sample.Duration != wantDur {
		t.Fatalf("duration=%v want %v", sample.Duration, wantDur)
	}
	if sample.Speed < 1.009 || sample.Speed > 1.011 {
		t.Fatalf("speed=%v want ~1.01", sample.Speed)
	}
	if sample.BitrateKbps < 203.3 || sample.BitrateKbps > 203.5 {
		t.Fatalf("bitrate=%v want ~203.4", sample.BitrateKbps)
	}
}

func TestParseFFmpegProgressLine_CarriageReturnStyle(t *testing.T) {
	line := "frame=  100 fps=0.0 q=-1.0 size=     256kB time=00:00:03.20 bitrate= 655.4kbits/s speed=6.4x"
	sample := parseFFmpegProgressLine(line)
	if !sample.Valid {
		t.Fatal("expected valid sample")
	}
	if sample.SizeBytes != 256*1024 {
		t.Fatalf("size=%d", sample.SizeBytes)
	}
	if sample.Duration != 3*time.Second+200*time.Millisecond {
		t.Fatalf("duration=%v", sample.Duration)
	}
}

func TestParseFFmpegProgressLine_NAIgnored(t *testing.T) {
	line := "frame=    0 fps=0.0 q=0.0 size=N/A time=00:00:00.00 bitrate=N/A speed=N/A"
	sample := parseFFmpegProgressLine(line)
	// time=00:00:00.00 still parses as Valid with zero-ish duration; size/speed N/A skipped
	if sample.SizeBytes != 0 {
		t.Fatalf("size should be 0 for N/A, got %d", sample.SizeBytes)
	}
	if sample.Speed != 0 {
		t.Fatalf("speed should be 0 for N/A, got %v", sample.Speed)
	}
}

func TestParseFFmpegProgressLine_NonProgress(t *testing.T) {
	sample := parseFFmpegProgressLine("Input #0, hls, from 'https://example.com/index.m3u8':")
	if sample.Valid {
		t.Fatal("non-progress line should be invalid")
	}
}

func TestParseFFmpegProgressLine_ProgressKV(t *testing.T) {
	cases := []struct {
		line string
		check func(*testing.T, ffmpegProgressSample)
	}{
		{
			line: "total_size=1048576",
			check: func(t *testing.T, s ffmpegProgressSample) {
				if !s.Valid || s.SizeBytes != 1048576 {
					t.Fatalf("got %+v", s)
				}
			},
		},
		{
			line: "out_time_ms=41200000",
			check: func(t *testing.T, s ffmpegProgressSample) {
				if !s.Valid || s.Duration != 41*time.Second+200*time.Millisecond {
					t.Fatalf("got %+v", s)
				}
			},
		},
		{
			line: "speed=0.95x",
			check: func(t *testing.T, s ffmpegProgressSample) {
				if !s.Valid || s.Speed < 0.949 || s.Speed > 0.951 {
					t.Fatalf("got %+v", s)
				}
			},
		},
		{
			line: "progress=continue",
			check: func(t *testing.T, s ffmpegProgressSample) {
				if s.Valid {
					t.Fatalf("progress marker should not be a sample, got %+v", s)
				}
			},
		},
	}
	for _, tc := range cases {
		t.Run(tc.line, func(t *testing.T) {
			tc.check(t, parseFFmpegProgressLine(tc.line))
		})
	}
}

func TestProgressStore_UpdatePercentETA(t *testing.T) {
	store := newProgressStore()
	key := progressKeyVOD("alice", "v123")
	store.Start(key, ProgressMeta{
		Channel:       "alice",
		Kind:          DownloadKindVOD,
		VodID:         "v123",
		Title:         "Cool Stream",
		TotalDuration: 100 * time.Second,
	})
	store.Update(key, ffmpegProgressSample{
		SizeBytes: 10 * 1024 * 1024,
		Duration:  40 * time.Second,
		Speed:     2.0,
		Valid:     true,
	})

	p, ok := store.Get(key)
	if !ok {
		t.Fatal("expected progress entry")
	}
	if p.Percent == nil || *p.Percent < 39.9 || *p.Percent > 40.1 {
		t.Fatalf("percent=%v want ~40", p.Percent)
	}
	if p.ETA == nil || *p.ETA != 30*time.Second {
		t.Fatalf("eta=%v want 30s", p.ETA)
	}

	store.End(key)
	if _, ok := store.Get(key); ok {
		t.Fatal("expected entry removed")
	}
}

func TestProgressStore_SnapshotSorted(t *testing.T) {
	store := newProgressStore()
	store.Start(progressKeyLive("zack"), ProgressMeta{Channel: "zack", Kind: DownloadKindLive})
	store.Start(progressKeyLive("alice"), ProgressMeta{Channel: "alice", Kind: DownloadKindLive})
	store.Start(progressKeyVOD("alice", "9"), ProgressMeta{Channel: "alice", Kind: DownloadKindVOD, VodID: "9"})

	snap := store.Snapshot()
	if len(snap) != 3 {
		t.Fatalf("len=%d", len(snap))
	}
	if snap[0].Channel != "alice" || snap[0].Kind != DownloadKindLive {
		t.Fatalf("first=%+v", snap[0])
	}
	if snap[1].Channel != "alice" || snap[1].Kind != DownloadKindVOD {
		t.Fatalf("second=%+v", snap[1])
	}
	if snap[2].Channel != "zack" {
		t.Fatalf("third=%+v", snap[2])
	}
}

func TestFFmpegLogWriter_ParsesCRSeparatedLines(t *testing.T) {
	store := newProgressStore()
	key := progressKeyLive("day9tv")
	store.Start(key, ProgressMeta{Channel: "day9tv", Kind: DownloadKindLive})
	w := newFFmpegLogWriter(key, store)
	w.debugInterval = time.Hour // silence debug noise in test

	payload := "frame= 10 fps=30 size=   128kB time=00:00:01.00 bitrate=100.0kbits/s speed=1.00x\r" +
		"frame= 20 fps=30 size=   256kB time=00:00:02.00 bitrate=100.0kbits/s speed=1.00x\r"
	if _, err := w.Write([]byte(payload)); err != nil {
		t.Fatal(err)
	}

	p, ok := store.Get(key)
	if !ok {
		t.Fatal("missing progress")
	}
	if p.SizeBytes != 256*1024 {
		t.Fatalf("size=%d want 256KiB", p.SizeBytes)
	}
	if p.Duration != 2*time.Second {
		t.Fatalf("duration=%v", p.Duration)
	}
	if !strings.Contains(w.String(), "size=") {
		t.Fatalf("writer should retain log tail, got %q", w.String())
	}
}

func TestFormatDownloadProgress(t *testing.T) {
	pct := 45.0
	eta := 24 * time.Minute
	s := formatDownloadProgress(DownloadProgress{
		Channel:   "bob",
		Kind:      DownloadKindVOD,
		Title:     "Highlights",
		SizeBytes: 800 * 1024 * 1024,
		Duration:  20 * time.Minute,
		Speed:     0.95,
		Percent:   &pct,
		ETA:       &eta,
	})
	for _, want := range []string{"[bob]", "vod", "Highlights", "45.0%", "size=", "time=", "speed=0.95x", "eta="} {
		if !strings.Contains(s, want) {
			t.Fatalf("format missing %q in %q", want, s)
		}
	}
}

func TestLogActiveDownloadSummary(t *testing.T) {
	store := newProgressStore()
	store.Start(progressKeyLive("alice"), ProgressMeta{Channel: "alice", Kind: DownloadKindLive})
	store.Update(progressKeyLive("alice"), ffmpegProgressSample{
		SizeBytes: 1024,
		Duration:  time.Minute,
		Speed:     1,
		Valid:     true,
	})

	out := captureLogs(func() {
		logActiveDownloadSummary(store)
	})
	if !strings.Contains(out, "Active Downloads:") {
		t.Fatalf("missing header: %s", out)
	}
	if !strings.Contains(out, "[alice] live") {
		t.Fatalf("missing entry: %s", out)
	}
}
