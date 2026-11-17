import io
import logging
import re
import warnings

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


def test_other_libraries_log_warnings_through_the_same_handlers(tmp_path):
    cfg = setup_logging("debug", "file", "", str(tmp_path))
    logging.getLogger("uvicorn.error").warning("third-party-warning")
    logging.getLogger("some.library").info("third-party-info")
    lines = (tmp_path / "streamdl.log").read_text().splitlines()
    assert lines[-1].endswith("] WARNING third-party-warning")
    assert not any("third-party-info" in line for line in lines)
    handlers = list(cfg.handlers)
    cfg.close()
    assert not set(handlers) & set(logging.getLogger().handlers)
    logging.getLogger("uvicorn.error").warning("after-close")
    assert "after-close" not in (tmp_path / "streamdl.log").read_text()


def test_line_format(tmp_path):
    setup_logging("info", "file", "", str(tmp_path))
    logging.getLogger("streamdl").info("hello")
    line = (tmp_path / "streamdl.log").read_text().splitlines()[-1]
    assert re.fullmatch(r"\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\] INFO hello", line)


def test_level_names_stay_upper_case_after_importing_streamlink(tmp_path):
    import streamlink.logger  # noqa: F401  renames the levels to lower case

    setup_logging("info", "file", "", str(tmp_path))
    logging.getLogger("streamdl").warning("hello")
    line = (tmp_path / "streamdl.log").read_text().splitlines()[-1]
    assert line.endswith("] WARNING hello")


def test_setup_closes_replaced_handlers(tmp_path):
    first = setup_logging("info", "file", str(tmp_path / "a.log"), str(tmp_path))
    old = first.handlers[0]
    setup_logging("info", "stdout", "", str(tmp_path))
    assert old.stream is None


def test_setup_leaves_other_root_handlers_alone(tmp_path, caplog):
    setup_logging("info", "file", str(tmp_path / "a.log"), str(tmp_path))
    setup_logging("info", "file", str(tmp_path / "b.log"), str(tmp_path))
    logging.getLogger("streamdl").warning("still-captured")
    assert "still-captured" in caplog.text


def test_failed_setup_keeps_console_summary(tmp_path):
    setup_logging("info", "file", "", str(tmp_path))
    sink = log_setup.console_summary
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    with pytest.raises(OSError):
        setup_logging("info", "both", str(blocker / "x.log"), str(tmp_path))
    with pytest.raises(ValueError):
        setup_logging("info", "nope", "", str(tmp_path))
    assert log_setup.console_summary is sink is not None


def test_closing_a_replaced_config_keeps_the_new_summary(tmp_path):
    first = setup_logging("info", "file", str(tmp_path / "a.log"), str(tmp_path))
    second = setup_logging("info", "file", str(tmp_path / "b.log"), str(tmp_path))
    first.close()
    assert log_setup.console_summary is not None
    second.close()
    assert log_setup.console_summary is None


def test_write_console():
    buf = io.StringIO()
    log_setup.console_summary = buf
    log_setup.write_console("Active Downloads:\n")
    assert buf.getvalue() == "Active Downloads:\n"


def test_write_console_without_sink_is_noop():
    log_setup.write_console("ignored")


def test_python_warnings_are_logged_until_close(tmp_path):
    original = warnings.showwarning
    cfg = setup_logging("info", "file", "", str(tmp_path))
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        warnings.warn("library-warning", UserWarning)
    assert "] WARNING " in (tmp_path / "streamdl.log").read_text()
    assert "library-warning" in (tmp_path / "streamdl.log").read_text()
    cfg.close()
    assert warnings.showwarning is original


def test_close_resets_the_level_only_for_the_active_setup(tmp_path):
    logger = logging.getLogger("streamdl")
    first = setup_logging("debug", "file", str(tmp_path / "a.log"), str(tmp_path))
    second = setup_logging("error", "file", str(tmp_path / "b.log"), str(tmp_path))
    first.close()
    assert logger.level == logging.ERROR
    second.close()
    assert logger.level == logging.NOTSET
