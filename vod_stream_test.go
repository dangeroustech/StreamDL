package main

import "testing"

func TestVodStreamUser(t *testing.T) {
	tests := []struct {
		vodID string
		want  string
	}{
		{"v2807766672", "videos/2807766672"},
		{"2807766672", "videos/2807766672"},
		{"12345", "videos/12345"},
	}

	for _, tt := range tests {
		if got := vodStreamUser(tt.vodID); got != tt.want {
			t.Errorf("vodStreamUser(%q) = %q, want %q", tt.vodID, got, tt.want)
		}
	}
}
