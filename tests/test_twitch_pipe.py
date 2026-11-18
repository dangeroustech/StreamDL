import logging
import stat
from pathlib import Path

import pytest
from streamlink_cli.argparser import build_parser

from streamdl.notices import NoticeBuffer
from streamdl.twitch_pipe import (
    MAX_LINE_CHARS,
    TAIL_LINES,
    StreamlinkLog,
    ad_notice,
    build_streamlink_args,
    streamlink_config,
)

CMD = ("python", "-m", "streamlink")


@pytest.fixture
def notices():
    return NoticeBuffer()


# --- streamlink argv ------------------------------------------------------------


def test_streamlink_args_without_a_token():
    # fmt: off
    assert build_streamlink_args("alice", "720p", None, cmd=CMD) == [
        "python", "-m", "streamlink", "--stdout", "--loglevel", "info",
        "--http-timeout", "20", "--no-config", "twitch.tv/alice", "720p",
    ]
    # fmt: on


def test_streamlink_args_with_a_config_file():
    args = build_streamlink_args("alice", "best", "/tmp/x/config", cmd=CMD)
    assert args[-4:] == ["--config", "/tmp/x/config", "twitch.tv/alice", "best"]
    assert "--no-config" not in args


def test_streamlink_args_default_to_best():
    assert build_streamlink_args("alice", "", None, cmd=CMD)[-1] == "best"


# --- token config file ----------------------------------------------------------


def test_no_config_without_a_token():
    with streamlink_config("") as path:
        assert path is None


def test_config_file_holds_the_token_privately():
    with streamlink_config("abc123") as path:
        assert path is not None
        config = Path(path)
        assert config.read_text() == "twitch-api-header=Authorization=OAuth abc123\n"
        assert stat.S_IMODE(config.stat().st_mode) == 0o600
        assert stat.S_IMODE(config.parent.stat().st_mode) == 0o700
    assert not config.parent.exists()


def test_config_line_is_what_streamlink_parses():
    with streamlink_config("abc123") as path:
        line = Path(path).read_text().strip()
    assert build_parser().convert_arg_line_to_args(line) == [
        "--twitch-api-header=Authorization=OAuth abc123"
    ]


def test_config_dir_is_removed_on_error():
    with pytest.raises(RuntimeError):
        with streamlink_config("abc123") as path:
            raise RuntimeError("boom")
    assert not Path(path).parent.exists()


# --- streamlink stderr ----------------------------------------------------------


@pytest.mark.parametrize(
    "line,expected",
    [
        (
            "[plugins.twitch][info] Waiting for pre-roll ads to finish, be patient",
            "Skipping pre-roll ads",
        ),
        (
            "[plugins.twitch][info] Detected advertisement break of 30 seconds",
            "Skipping a 30s ad break",
        ),
        (
            "[plugins.twitch][info] Detected advertisement break of 1 second",
            "Skipping a 1s ad break",
        ),
        ("[cli][info] Opening stream: best (hls)", None),
        ("", None),
    ],
)
def test_ad_notice(line, expected):
    assert ad_notice(line) == expected


def test_streamlink_log_keeps_a_sanitised_tail(notices):
    sl = StreamlinkLog("alice", notices)
    sl.write(
        b"[cli][info] Opening stream: best (hls)\n"
        b"[cli][error] GET https://x/a.m3u8?sig=s&token=t failed\n"
    )
    assert sl.tail() == (
        "[cli][info] Opening stream: best (hls)\n"
        "[cli][error] GET https://x/a.m3u8?sig=<redacted>&token=<redacted> failed"
    )


def test_streamlink_log_tail_is_bounded(notices):
    sl = StreamlinkLog("alice", notices)
    sl.write(b"".join(b"line %d\n" % i for i in range(200)))
    sl.write(b"x" * 10000 + b"\n")
    lines = sl.tail().split("\n")
    assert len(lines) == TAIL_LINES
    assert lines[0] == "line 151"
    assert lines[-1] == "x" * MAX_LINE_CHARS


def test_streamlink_log_joins_lines_split_across_chunks(notices):
    sl = StreamlinkLog("alice", notices)
    sl.write(b"[plugins.twitch][info] Detected advertise")
    sl.write(b"ment break of 30 seconds\r\n")
    sl.write(b"no newline at the end")
    sl.close()
    assert sl.tail().split("\n") == [
        "[plugins.twitch][info] Detected advertisement break of 30 seconds",
        "no newline at the end",
    ]
    assert [(n.level, n.message) for n in notices.pending()] == [
        (logging.INFO, "Skipping a 30s ad break")
    ]


def test_streamlink_log_turns_ad_messages_into_info_notices(notices):
    sl = StreamlinkLog("alice", notices)
    sl.write(
        b"[plugins.twitch][info] Waiting for pre-roll ads to finish, be patient\n"
        b"[plugins.twitch][info] Detected advertisement break of 15 seconds\n"
    )
    assert [(n.level, n.channel, n.message) for n in notices.pending()] == [
        (logging.INFO, "alice", "Skipping pre-roll ads"),
        (logging.INFO, "alice", "Skipping a 15s ad break"),
    ]


def test_streamlink_log_redacts_the_token(notices, caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    sl = StreamlinkLog("alice", notices, token="sekrit")
    sl.write(b"[cli][debug] header Authorization: OAuth sekrit\n")
    assert "OAuth <redacted>" in sl.tail()
    assert "sekrit" not in sl.tail()
    assert "sekrit" not in caplog.text


def test_streamlink_log_reports_a_rejected_token_once(notices):
    sl = StreamlinkLog("alice", notices, token="sekrit")
    sl.write(b'error: Unauthorized: The "Authorization" token is invalid.\n' * 2)
    assert [(n.level, n.message) for n in notices.pending()] == [
        (
            logging.ERROR,
            "Twitch rejected TWITCH_OAUTH_TOKEN: "
            'error: Unauthorized: The "Authorization" token is invalid.',
        )
    ]


def test_streamlink_log_ignores_unauthorized_without_a_token(notices):
    sl = StreamlinkLog("alice", notices)
    sl.write(b"error: Unauthorized: nope\n")
    assert notices.pending() == []


def test_streamlink_log_logs_each_line_at_debug(notices, caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    sl = StreamlinkLog("alice", notices)
    sl.write(b"[cli][info] Opening stream: best (hls)\n")
    [record] = [r for r in caplog.records if r.name == "streamdl.twitch_pipe"]
    assert record.levelno == logging.DEBUG
    assert record.getMessage() == (
        "streamlink [alice]: [cli][info] Opening stream: best (hls)"
    )
