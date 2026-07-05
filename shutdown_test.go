package main

import (
	"sync"
	"testing"
	"time"
)

// TestDownloadWgShutdownDrain verifies the shutdown pattern used for live downloads:
// wait on a WaitGroup instead of counting channel receives. This guards against the
// hang described in issue #583 where a snapshot of activeUsers could expect more
// response signals than goroutines actually send.
func TestDownloadWgShutdownDrain(t *testing.T) {
	var wg sync.WaitGroup
	waitDone := make(chan struct{})

	wg.Add(2)
	go func() {
		wg.Wait()
		close(waitDone)
	}()

	go func() {
		defer wg.Done()
		time.Sleep(10 * time.Millisecond)
	}()
	go func() {
		defer wg.Done()
		time.Sleep(20 * time.Millisecond)
	}()

	select {
	case <-waitDone:
	case <-time.After(time.Second):
		t.Fatal("WaitGroup wait did not return after concurrent goroutine exits")
	}
}
