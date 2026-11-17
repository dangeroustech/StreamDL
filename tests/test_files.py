import errno
import logging
import os
import stat

import pytest

from streamdl.files import (
    create_dir_with_umask,
    get_umask,
    is_cross_device,
    move_file,
    sanitize_filename,
)


def test_umask_default():
    assert get_umask({}) == 0o022


def test_umask_custom():
    assert get_umask({"UMASK": "002"}) == 0o002


def test_umask_invalid(caplog):
    caplog.set_level(logging.WARNING, logger="streamdl")
    assert get_umask({"UMASK": "9z"}) == 0o022
    assert "Invalid UMASK" in caplog.text


@pytest.mark.parametrize("raw", [" 027", "0o27", "0_27", "+0o27", "20000000000"])
def test_umask_rejects_what_go_parseint_rejects(raw):
    assert get_umask({"UMASK": raw}) == 0o022


def test_create_dir_applies_umask_to_new_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("UMASK", "027")
    target = tmp_path / "a" / "b"
    create_dir_with_umask(str(target))
    for d in (tmp_path / "a", target):
        assert stat.S_IMODE(d.stat().st_mode) == 0o750


def test_create_dir_leaves_existing_dirs_alone(tmp_path, monkeypatch):
    d = tmp_path / "x"
    d.mkdir()
    os.chmod(d, 0o700)
    monkeypatch.setenv("UMASK", "000")
    create_dir_with_umask(str(d))
    assert stat.S_IMODE(d.stat().st_mode) == 0o700


def test_create_dir_rejects_files(tmp_path):
    f = tmp_path / "f"
    f.write_text("")
    with pytest.raises(FileExistsError):
        create_dir_with_umask(str(f))


def test_move_same_filesystem(tmp_path):
    src, dst = tmp_path / "src.txt", tmp_path / "out" / "dst.txt"
    src.write_bytes(b"hello world")
    move_file(str(src), str(dst))
    assert not src.exists()
    assert dst.read_bytes() == b"hello world"


def test_move_cross_device_copies(tmp_path):
    src, dst = tmp_path / "src2.txt", tmp_path / "sub" / "dst2.txt"
    temp = dst.parent / ".tmp.dst2.txt"
    src.write_bytes(b"cross-device")
    calls = []

    def rename(old, new):
        calls.append((old, new))
        if (old, new) == (str(src), str(dst)):
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        os.rename(old, new)

    move_file(str(src), str(dst), rename=rename)
    assert len(calls) == 2
    assert not src.exists()
    assert dst.read_bytes() == b"cross-device"
    assert not temp.exists()


def test_move_cross_device_final_rename_failure_cleans_up(tmp_path):
    src, dst = tmp_path / "src3.txt", tmp_path / "dst3.txt"
    temp = tmp_path / ".tmp.dst3.txt"
    src.write_bytes(b"keep original on failure")

    def rename(old, new):
        if (old, new) == (str(src), str(dst)):
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        raise OSError("rename failed")

    with pytest.raises(OSError, match="rename failed"):
        move_file(str(src), str(dst), rename=rename)
    assert src.exists()
    assert not dst.exists()
    assert not temp.exists()


def test_move_other_errors_propagate(tmp_path):
    src, dst = tmp_path / "a.txt", tmp_path / "b.txt"
    src.write_bytes(b"x")

    def rename(old, new):
        raise PermissionError(errno.EACCES, "denied")

    with pytest.raises(PermissionError):
        move_file(str(src), str(dst), rename=rename)
    assert src.exists()


def test_cross_device_detection():
    assert is_cross_device(OSError(errno.EXDEV, "x"))
    assert is_cross_device(OSError("invalid cross-device link: EXDEV"))
    assert not is_cross_device(OSError(errno.EACCES, "denied"))


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("a/b:c", "a_b_c"),
        ('x*?"<>|y', "x_y"),
        ("  ..title.. ", "title"),
        ("a//b", "a_b"),
        ("line\nbreak", "line_break"),
        ("Just Chatting!", "Just Chatting!"),
        ("", ""),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_truncates_to_100_bytes():
    assert sanitize_filename("x" * 150) == "x" * 100
    assert sanitize_filename("é" * 60) == "é" * 50


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("a\ud800b", "a_b"),
        ("a\x00b", "a_b"),
        ("a\x1fb\tc", "a_b_c"),
        ("\x00\ud800", ""),
    ],
)
def test_sanitize_filename_is_total(raw, expected):
    assert sanitize_filename(raw) == expected


def test_move_cross_device_cleanup_error_does_not_mask_failure(tmp_path, monkeypatch):
    src, dst = tmp_path / "src4.txt", tmp_path / "dst4.txt"
    temp = str(tmp_path / ".tmp.dst4.txt")
    src.write_bytes(b"x")
    real_remove = os.remove

    def rename(old, new):
        if (old, new) == (str(src), str(dst)):
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        raise OSError("rename failed")

    def remove(path):
        if path == temp:
            raise PermissionError(errno.EACCES, "denied")
        real_remove(path)

    monkeypatch.setattr(os, "remove", remove)
    with pytest.raises(OSError, match="rename failed"):
        move_file(str(src), str(dst), rename=rename)
    assert src.exists()
