package main

import (
	"fmt"
	"strings"
	"sync"

	log "github.com/sirupsen/logrus"
)

// TickNotice is a user-facing message buffered until the end of a tick.
type TickNotice struct {
	Level   log.Level
	Channel string
	Message string
}

// Noticer collects actionable notices and flushes them after the tick wait line.
type Noticer interface {
	Warn(channel, message string)
	Error(channel, message string)
	ClearChannel(channel string)
	Flush(waitSeconds int)
}

type noticeBuffer struct {
	mu       sync.Mutex
	pending  []TickNotice
	surfaced map[string]struct{}
}

func newNoticeBuffer() *noticeBuffer {
	return &noticeBuffer{surfaced: make(map[string]struct{})}
}

func (b *noticeBuffer) dedupeKey(channel, message string) string {
	return channel + "|" + message
}

func (b *noticeBuffer) add(level log.Level, channel, message string) {
	channel = strings.TrimSpace(channel)
	message = strings.TrimSpace(message)
	if channel == "" || message == "" {
		return
	}

	b.mu.Lock()
	defer b.mu.Unlock()

	key := b.dedupeKey(channel, message)
	if _, ok := b.surfaced[key]; ok {
		return
	}
	for _, n := range b.pending {
		if b.dedupeKey(n.Channel, n.Message) == key {
			return
		}
	}
	b.pending = append(b.pending, TickNotice{Level: level, Channel: channel, Message: message})
}

func (b *noticeBuffer) Warn(channel, message string) {
	b.add(log.WarnLevel, channel, message)
}

func (b *noticeBuffer) Error(channel, message string) {
	b.add(log.ErrorLevel, channel, message)
}

// ClearChannel resets deduplication for a channel when a live session ends.
func (b *noticeBuffer) ClearChannel(channel string) {
	b.mu.Lock()
	defer b.mu.Unlock()

	prefix := channel + "|"
	for key := range b.surfaced {
		if strings.HasPrefix(key, prefix) {
			delete(b.surfaced, key)
		}
	}
}

// Flush logs the wait line and any buffered notices, then marks them as surfaced.
func (b *noticeBuffer) Flush(waitSeconds int) {
	b.mu.Lock()
	pending := append([]TickNotice(nil), b.pending...)
	b.pending = b.pending[:0]
	b.mu.Unlock()

	log.Infof("Waiting %ds until next check...", waitSeconds)
	if len(pending) == 0 {
		return
	}

	log.Info("--- notices ---")
	for _, n := range pending {
		formatted := fmt.Sprintf("[%s] %s", n.Channel, n.Message)
		switch n.Level {
		case log.ErrorLevel, log.FatalLevel, log.PanicLevel:
			log.Error(formatted)
		default:
			log.Warn(formatted)
		}

		b.mu.Lock()
		b.surfaced[b.dedupeKey(n.Channel, n.Message)] = struct{}{}
		b.mu.Unlock()
	}
}

// tickNotices is the process-wide notice buffer; tests may replace it.
var tickNotices Noticer = newNoticeBuffer()
