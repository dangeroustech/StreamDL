package main

import (
	"bytes"
	"strings"
	"testing"

	log "github.com/sirupsen/logrus"
)

func captureLogs(fn func()) string {
	var buf bytes.Buffer
	orig := log.StandardLogger().Out
	log.SetOutput(&buf)
	defer log.SetOutput(orig)
	fn()
	return buf.String()
}

func TestNoticeBuffer_FlushOrderAndDedup(t *testing.T) {
	nb := newNoticeBuffer()

	out := captureLogs(func() {
		nb.Warn("day9tv", "Requested quality 1080p60 unavailable")
		nb.Warn("day9tv", "Requested quality 1080p60 unavailable")
		nb.Flush(60)
	})

	if !strings.Contains(out, "Waiting 60s until next check") {
		t.Fatalf("expected wait line in output, got:\n%s", out)
	}
	waitIdx := strings.Index(out, "Waiting 60s until next check")
	noticeIdx := strings.Index(out, "[day9tv] Requested quality 1080p60 unavailable")
	if noticeIdx == -1 {
		t.Fatalf("expected notice in output, got:\n%s", out)
	}
	if noticeIdx < waitIdx {
		t.Fatalf("notice should appear after wait line, got:\n%s", out)
	}
	if strings.Count(out, "[day9tv] Requested quality 1080p60 unavailable") != 1 {
		t.Fatalf("duplicate notice should be deduped within tick, got:\n%s", out)
	}

	out = captureLogs(func() {
		nb.Warn("day9tv", "Requested quality 1080p60 unavailable")
		nb.Flush(60)
	})
	if strings.Contains(out, "[day9tv]") {
		t.Fatalf("notice should stay suppressed after surfacing, got:\n%s", out)
	}

	nb.ClearChannel("day9tv")
	out = captureLogs(func() {
		nb.Warn("day9tv", "Requested quality 1080p60 unavailable")
		nb.Flush(60)
	})
	if !strings.Contains(out, "[day9tv] Requested quality 1080p60 unavailable") {
		t.Fatalf("notice should reappear after ClearChannel, got:\n%s", out)
	}
}

func TestNoticeBuffer_ErrorLevel(t *testing.T) {
	nb := newNoticeBuffer()
	out := captureLogs(func() {
		nb.Error("kickuser", "Channel is offline")
		nb.Flush(5)
	})
	if !strings.Contains(out, "level=error") {
		t.Fatalf("expected error level log, got:\n%s", out)
	}
	if !strings.Contains(out, "[kickuser] Channel is offline") {
		t.Fatalf("expected formatted notice, got:\n%s", out)
	}
}

func TestNoticeBuffer_EmptyInputIgnored(t *testing.T) {
	nb := newNoticeBuffer()
	out := captureLogs(func() {
		nb.Warn("", "message")
		nb.Warn("channel", "")
		nb.Flush(1)
	})
	if strings.Contains(out, "--- notices ---") {
		t.Fatalf("empty notices should not produce notice block, got:\n%s", out)
	}
}
