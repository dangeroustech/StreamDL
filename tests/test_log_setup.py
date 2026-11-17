import io
import logging
import re

import pytest

from streamdl import log_setup
from streamdl.log_setup import LogDest, parse_level, parse_log_dest, setup_logging


@pytest.mark.parametrize(
    "value,expected",
    [
        ("", LogDest.FILE),
        ("file", LogDest.FILE),
        ("FILE", LogDest.FILE),
        ("stdout", LogDest.STDOUT),
        ("console", LogDest.STDOUT),
        ("container", LogDest.STDOUT),
        ("both", LogDest.BOTH),
        ("all", LogDest.BOTH),
    ],
)
def test_parse_log_dest(value, expected):
    assert parse_log_dest(value) is expected


def test_parse_log_dest_invalid():
    with pytest.raises(ValueError):
        parse_log_dest("nope")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("trace", logging.DEBUG),
        ("debug", logging.DEBUG),
        ("INFO", logging.INFO),
        ("warn", logging.WARNING),
        ("error", logging.ERROR),
        ("fatal", logging.CRITICAL),
        ("bogus", logging.INFO),
    ],
)
def test_parse_level(value, expected):
    assert parse_level(value) == expected


def test_file_default_path_and_console_summary(tmp_path):
    cfg = setup_logging("info", "file", "", str(tmp_path))
    assert cfg.file_path == str(tmp_path / "streamdl.log")
    assert log_setup.console_summary is not None
    logging.getLogger("streamdl").info("hello-file-only")
    assert "hello-file-only" in (tmp_path / "streamdl.log").read_text()
    cfg.close()
    assert log_setup.console_summary is None


def test_stdout_has_no_console_summary_or_file(tmp_path):
    cfg = setup_logging("debug", "stdout", "", str(tmp_path))
    assert log_setup.console_summary is None
    assert cfg.file_path == ""
    assert not (tmp_path / "streamdl.log").exists()


def test_both_writes_file_and_stdout(tmp_path, capsys):
    path = tmp_path / "custom.log"
    setup_logging("info", "both", str(path), str(tmp_path))
    assert log_setup.console_summary is None
    logging.getLogger("streamdl").info("hello-both")
    assert "hello-both" in path.read_text()
    assert "hello-both" in capsys.readouterr().out


def test_child_loggers_use_the_same_handlers(tmp_path):
    setup_logging("debug", "file", "", str(tmp_path))
    logging.getLogger("streamdl.recorder").debug("from-a-module")
    assert "from-a-module" in (tmp_path / "streamdl.log").read_text()


def test_line_format(tmp_path):
    setup_logging("info", "file", "", str(tmp_path))
    logging.getLogger("streamdl").info("hello")
    line = (tmp_path / "streamdl.log").read_text().splitlines()[-1]
    assert re.fullmatch(r"\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\] INFO hello", line)


def test_write_console():
    buf = io.StringIO()
    log_setup.console_summary = buf
    log_setup.write_console("Active Downloads:\n")
    assert buf.getvalue() == "Active Downloads:\n"


def test_write_console_without_sink_is_noop():
    log_setup.write_console("ignored")
