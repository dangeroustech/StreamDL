"""Small helpers for child processes."""

from __future__ import annotations

import os
import signal


def describe_exit(returncode: int) -> str:
    """Describe a child's exit like the v3 client did: 'exit status 1', 'signal: killed'."""
    if returncode >= 0:
        return f"exit status {returncode}"
    signum = -returncode
    # Go names only the classic signals; others (real-time, out of range) are "signal N".
    name = signal.strsignal(signum) if signum < 32 else None
    return f"signal: {name.lower()}" if name else f"signal: signal {signum}"


def kill_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
