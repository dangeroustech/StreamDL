package main

import (
	"errors"
	"io"
	"os"
	"path/filepath"
	"testing"

	log "github.com/sirupsen/logrus"
)

func TestMain(m *testing.M) {
    // Silence log output during tests to keep output readable
    log.SetOutput(io.Discard)
    os.Exit(m.Run())
}

func TestMoveFile_RenameSameFS_Succeeds(t *testing.T) {
    t.Cleanup(func() { renameFunc = os.Rename })

    dir := t.TempDir()
    src := filepath.Join(dir, "src.txt")
    dst := filepath.Join(dir, "dst.txt")

    content := []byte("hello world")
    if err := os.WriteFile(src, content, 0644); err != nil {
        t.Fatalf("write src: %v", err)
    }

    if err := moveFile(src, dst); err != nil {
        t.Fatalf("moveFile error: %v", err)
    }

    if _, err := os.Stat(src); !os.IsNotExist(err) {
        t.Fatalf("expected src removed, got err=%v", err)
    }
    got, err := os.ReadFile(dst)
    if err != nil {
        t.Fatalf("read dst: %v", err)
    }
    if string(got) != string(content) {
        t.Fatalf("content mismatch: got %q want %q", string(got), string(content))
    }
}

func TestMoveFile_CrossDeviceCopy_Succeeds(t *testing.T) {
    dir := t.TempDir()
    src := filepath.Join(dir, "src2.txt")
    dst := filepath.Join(dir, "dst2.txt")
    temp := filepath.Join(filepath.Dir(dst), ".tmp."+filepath.Base(dst))

    content := []byte("cross-device")
    if err := os.WriteFile(src, content, 0644); err != nil {
        t.Fatalf("write src: %v", err)
    }

    // Stub rename to force EXDEV on first call, then perform real rename for temp->dst
    calls := 0
    renameFunc = func(oldPath, newPath string) error {
        calls++
        if oldPath == src && newPath == dst {
            return syscallEXDEV()
        }
        if oldPath == temp && newPath == dst {
            return os.Rename(oldPath, newPath)
        }
        return nil
    }
    t.Cleanup(func() { renameFunc = os.Rename })

    if err := moveFile(src, dst); err != nil {
        t.Fatalf("moveFile error: %v", err)
    }
    if calls < 2 {
        t.Fatalf("expected at least 2 rename calls, got %d", calls)
    }
    if _, err := os.Stat(src); !os.IsNotExist(err) {
        t.Fatalf("expected src removed, got err=%v", err)
    }
    got, err := os.ReadFile(dst)
    if err != nil {
        t.Fatalf("read dst: %v", err)
    }
    if string(got) != string(content) {
        t.Fatalf("content mismatch: got %q want %q", string(got), string(content))
    }
}

func TestMoveFile_CrossDeviceCopy_RenameFail_CleansUp(t *testing.T) {
    dir := t.TempDir()
    src := filepath.Join(dir, "src3.txt")
    dst := filepath.Join(dir, "dst3.txt")
    temp := filepath.Join(filepath.Dir(dst), ".tmp."+filepath.Base(dst))

    content := []byte("keep original on failure")
    if err := os.WriteFile(src, content, 0644); err != nil {
        t.Fatalf("write src: %v", err)
    }

    // First EXDEV, then fail final rename with EPERM (or generic error)
    renameFunc = func(oldPath, newPath string) error {
        if oldPath == src && newPath == dst {
            return syscallEXDEV()
        }
        if oldPath == temp && newPath == dst {
            return errors.New("rename failed")
        }
        return nil
    }
    t.Cleanup(func() { renameFunc = os.Rename })

    if err := moveFile(src, dst); err == nil {
        t.Fatalf("expected error but got nil")
    }

    // Original should still exist
    if _, err := os.Stat(src); err != nil {
        t.Fatalf("expected src to remain, stat err=%v", err)
    }
    // Destination should not exist
    if _, err := os.Stat(dst); !os.IsNotExist(err) {
        t.Fatalf("expected dst not to exist, got err=%v", err)
    }
    // Temp file should be cleaned up by defer
    if _, err := os.Stat(temp); !os.IsNotExist(err) {
        // Read out for debugging if present
        if b, rerr := os.ReadFile(temp); rerr == nil {
            t.Logf("temp file exists with size=%d", len(b))
        }
        t.Fatalf("expected temp to be removed, got err=%v", err)
    }
}

// syscallEXDEV returns an error equivalent to a cross-device link error
func syscallEXDEV() error {
    // Use os.Link error as proxy; we'll wrap a message that contains exdev
    return errors.New("invalid cross-device link: EXDEV")
}


