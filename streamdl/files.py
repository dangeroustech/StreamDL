"""Directory creation, cross-filesystem moves and filename cleanup."""

from __future__ import annotations

import contextlib
import errno
import logging
import os
import re
import shutil
import stat
from collections.abc import Callable, Mapping

log = logging.getLogger(__name__)

DEFAULT_UMASK = 0o022
# Path separators, characters Windows/SMB reject, and every C0 control char (incl. NUL).
_UNSAFE = str.maketrans({c: "_" for c in '/\\:*?"<>|' + "".join(map(chr, range(0x20)))})
_RE_OCTAL = re.compile(r"[+-]?[0-7]+")
_INT32_MIN, _INT32_MAX = -(2**31), 2**31 - 1


def get_umask(env: Mapping[str, str] | None = None) -> int:
    """UMASK env var as octal; invalid values warn and fall back to 022.

    Parsed like Go's strconv.ParseInt(s, 8, 32): no whitespace, "0o" prefix or
    "_" separators, and the value must fit in an int32.
    """
    value = (os.environ if env is None else env).get("UMASK", "") or "022"
    if _RE_OCTAL.fullmatch(value):
        umask = int(value, 8)
        if _INT32_MIN <= umask <= _INT32_MAX:
            return umask
    log.warning("Invalid UMASK value %s, using default 022", value)
    return DEFAULT_UMASK


def create_dir_with_umask(path: str) -> None:
    """Create path and any missing parents with mode 0777 minus UMASK.

    Existing directories are left alone. Modes are set with chmod rather than by
    changing the process umask, so this is safe to call from worker threads.

    Like Go's os.MkdirAll, a directory created concurrently by another caller is
    accepted (that caller sets its mode); only a non-directory in the way raises.
    """
    if os.path.isdir(path):
        return
    perms = 0o777 & ~get_umask()
    missing = []
    current = os.path.abspath(path)
    while not os.path.exists(current):
        missing.append(current)
        current = os.path.dirname(current)
    for directory in reversed(missing):
        try:
            os.mkdir(directory)
        except FileExistsError:
            if not os.path.isdir(directory):
                raise _not_a_directory(directory) from None
            continue  # created meanwhile by another caller
        os.chmod(directory, perms)
    if not os.path.isdir(path):
        raise _not_a_directory(path)


def _not_a_directory(path: str) -> FileExistsError:
    return FileExistsError(errno.EEXIST, "exists and is not a directory", path)


def is_cross_device(err: OSError) -> bool:
    if err.errno == errno.EXDEV:
        return True
    text = str(err).lower()
    return "cross-device" in text or "exdev" in text


def move_file(
    old_path: str,
    new_path: str,
    *,
    rename: Callable[[str, str], None] = os.rename,
) -> None:
    """Move a file, falling back to copy + fsync + rename across filesystems.

    The source is deleted only after the copy has been renamed into place.
    """
    log.info("Moving file from %s to %s", old_path, new_path)
    target_dir = os.path.dirname(new_path)
    create_dir_with_umask(target_dir)

    try:
        rename(old_path, new_path)
        log.info("Atomically renamed %s to %s", old_path, new_path)
        return
    except OSError as e:
        if not is_cross_device(e):
            log.debug("rename failed with a non-cross-device error: %s", e)
            raise

    temp_path = os.path.join(target_dir, ".tmp." + os.path.basename(new_path))
    try:
        with open(old_path, "rb") as src:
            perms = stat.S_IMODE(os.fstat(src.fileno()).st_mode) & ~get_umask()
            fd = os.open(temp_path, os.O_RDWR | os.O_CREAT | os.O_TRUNC, perms)
            with os.fdopen(fd, "wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
        rename(temp_path, new_path)
    finally:
        with contextlib.suppress(OSError):
            os.remove(temp_path)
    _fsync_dir(target_dir)
    os.remove(old_path)
    log.info("Moved file from %s to %s (cross-device)", old_path, new_path)


def _fsync_dir(path: str) -> None:
    """Best effort: persist the rename by syncing the directory entry."""
    with contextlib.suppress(OSError):
        fd = os.open(path or ".", os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def sanitize_filename(name: str) -> str:
    """Make a VOD title safe for a filename (same rules as v3, max 100 bytes)."""
    # Lone surrogates (possible in untrusted titles) become "?" and then "_".
    s = name.encode("utf-8", "replace").decode("utf-8").translate(_UNSAFE)
    while "__" in s:
        s = s.replace("__", "_")
    encoded = s.encode("utf-8")
    if len(encoded) > 100:
        s = encoded[:100].decode("utf-8", "ignore")
    return s.strip("_. ")
