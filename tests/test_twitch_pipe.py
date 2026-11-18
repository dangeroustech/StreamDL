import asyncio
import logging
import signal
import stat
from pathlib import Path

import pytest
from helpers import FAKE_FFMPEG, FAKE_STREAMLINK, streamlink_runs, wait_for_glob
from streamlink_cli.argparser import build_parser

from streamdl import twitch_pipe
from streamdl.ffmpeg import build_pipe_args
from streamdl.notices import NoticeBuffer
from streamdl.progress import FfmpegLogWriter, ProgressStore
from streamdl.settings import FfmpegOptions
from streamdl.twitch_pipe import (
    MAX_LINE_CHARS,
    TAIL_LINES,
    PipeResult,
    StreamlinkLog,
    ad_notice,
    build_streamlink_args,
    run_pipe,
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
        "--no-plugin-sideloading", "--http-timeout", "20", "--no-config",
        "twitch.tv/alice", "720p",
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


def test_streamlink_log_redacts_an_overlong_partial_line_whole(notices):
    sl = StreamlinkLog("alice", notices)
    sl.write(b"token=" + b"a" * 70000)
    sl.write(b"short line\n")
    lines = sl.tail().split("\n")
    assert lines[0].startswith("token=<redacted>")
    assert "a" * 100 not in sl.tail()


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
            'Unauthorized: The "Authorization" token is invalid.',
        )
    ]


def test_streamlink_log_does_not_blame_the_token_for_a_401_segment(notices):
    sl = StreamlinkLog("alice", notices, token="sekrit")
    sl.write(
        b"[stream.hls][error] Failed to fetch segment 12: "
        b"401 Client Error: Unauthorized for url: https://x/seg.ts\n"
    )
    assert notices.pending() == []


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


# --- run_pipe -------------------------------------------------------------------


@pytest.fixture
def spawned(monkeypatch):
    """Every process run_pipe starts, so tests can check none is left running."""
    procs = []
    spawn = asyncio.create_subprocess_exec

    async def recording_spawn(*args, **kwargs):
        proc = await spawn(*args, **kwargs)
        procs.append(proc)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", recording_spawn)
    return procs


@pytest.fixture
def pipe(tmp_path, ffmpeg_log, streamlink_log, notices):
    """run_pipe's arguments for the fakes, recording to tmp_path/rec.mp4."""
    return [
        build_streamlink_args("alice", "best", None, cmd=(FAKE_STREAMLINK,)),
        build_pipe_args(str(tmp_path / "rec.mp4"), FfmpegOptions(), ffmpeg=FAKE_FFMPEG),
        FfmpegLogWriter("live:alice", ProgressStore()),
        StreamlinkLog("alice", notices),
    ]


@pytest.fixture
def blocking_streamlink(tmp_path, monkeypatch):
    ready = tmp_path / "sl.ready"
    monkeypatch.setenv("FAKE_STREAMLINK_BLOCK", "1")
    monkeypatch.setenv("FAKE_STREAMLINK_READY", str(ready))
    return ready


async def test_streamlink_output_reaches_ffmpeg(pipe, spawned, tmp_path):
    result = await asyncio.wait_for(run_pipe(*pipe), 10)

    assert result == PipeResult(
        ffmpeg_rc=0, streamlink_rc=0, streamlink_tail="", streamlink_stopped=False
    )
    assert (tmp_path / "rec.mp4.stdin").read_bytes() == b"fake ts data"
    assert (tmp_path / "rec.mp4").read_bytes() == b"fake mp4"
    assert len(spawned) == 2
    assert all(p.returncode is not None for p in spawned)


async def test_streamlink_failure_is_reported_with_its_tail(pipe, monkeypatch):
    monkeypatch.setenv("FAKE_STREAMLINK_EXITS", "1")
    monkeypatch.setenv("FAKE_STREAMLINK_STDERR", "[cli][error] Stream ended badly")

    result = await asyncio.wait_for(run_pipe(*pipe), 10)

    assert result == PipeResult(0, 1, "[cli][error] Stream ended badly", False)


async def test_streamlink_is_stopped_when_ffmpeg_exits_first(
    pipe, spawned, blocking_streamlink, monkeypatch
):
    monkeypatch.setenv("FAKE_FFMPEG_SKIP_STDIN", "1")
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1")

    result = await asyncio.wait_for(run_pipe(*pipe), 10)

    assert result.ffmpeg_rc == 1
    assert result.streamlink_stopped is True
    # SIGTERM, or a broken pipe if FFmpeg was already gone when it wrote.
    assert result.streamlink_rc not in (0, -signal.SIGKILL)
    assert all(p.returncode is not None for p in spawned)


async def test_cancel_stops_streamlink_and_lets_ffmpeg_finish(
    pipe, spawned, blocking_streamlink, tmp_path
):
    task = asyncio.create_task(run_pipe(*pipe))
    await wait_for_glob(tmp_path, blocking_streamlink.name)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 10)

    ffmpeg, streamlink = spawned
    assert streamlink.returncode == -signal.SIGTERM
    assert ffmpeg.returncode == 0
    assert (tmp_path / "rec.mp4.stdin").read_bytes() == b"fake ts data"


async def test_streamlink_ignoring_sigterm_is_killed(
    pipe, spawned, blocking_streamlink, monkeypatch, tmp_path
):
    monkeypatch.setattr(twitch_pipe, "STREAMLINK_TERM_GRACE", 0.2)
    monkeypatch.setenv("FAKE_STREAMLINK_IGNORE_TERM", "1")
    task = asyncio.create_task(run_pipe(*pipe))
    await wait_for_glob(tmp_path, blocking_streamlink.name)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 10)

    ffmpeg, streamlink = spawned
    assert streamlink.returncode == -signal.SIGKILL
    assert ffmpeg.returncode == 0


async def test_missing_streamlink_raises_and_reaps_ffmpeg(pipe, spawned, tmp_path):
    pipe[0] = build_streamlink_args(
        "alice", "best", None, cmd=(str(tmp_path / "missing"),)
    )

    with pytest.raises(OSError):
        await asyncio.wait_for(run_pipe(*pipe), 10)

    [ffmpeg] = spawned
    assert ffmpeg.returncode is not None


async def test_missing_ffmpeg_raises_before_streamlink_starts(
    pipe, spawned, streamlink_log, tmp_path
):
    pipe[1] = build_pipe_args(
        str(tmp_path / "rec.mp4"), FfmpegOptions(), ffmpeg=str(tmp_path / "missing")
    )

    with pytest.raises(OSError):
        await asyncio.wait_for(run_pipe(*pipe), 10)

    assert spawned == []
    assert streamlink_runs(streamlink_log) == []


async def _wait_exited(proc, timeout=5.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while proc.returncode is None:
        assert loop.time() < deadline, f"pid {proc.pid} never exited"
        await asyncio.sleep(0.02)


async def test_reader_error_propagates_and_nothing_is_left_running(
    pipe, spawned, blocking_streamlink, monkeypatch
):
    # Ignoring SIGTERM, streamlink would hold run_pipe for the whole grace period
    # if the error were handled like an FFmpeg exit.
    monkeypatch.setenv("FAKE_STREAMLINK_IGNORE_TERM", "1")

    class BrokenWriter:
        def write(self, data):
            raise RuntimeError("writer bug")

    pipe[2] = BrokenWriter()
    loop = asyncio.get_running_loop()
    start = loop.time()

    with pytest.raises(RuntimeError, match="writer bug"):
        await asyncio.wait_for(run_pipe(*pipe), 10)

    assert loop.time() - start < 1
    assert len(spawned) == 2
    assert all(p.returncode is not None for p in spawned)


async def test_streamlink_reader_error_kills_both(
    pipe, spawned, blocking_streamlink, monkeypatch, notices
):
    monkeypatch.setenv("FAKE_STREAMLINK_IGNORE_TERM", "1")
    monkeypatch.setenv("FAKE_STREAMLINK_STDERR", "[cli][info] Opening stream")

    class BrokenLog(StreamlinkLog):
        def write(self, data):
            raise RuntimeError("log bug")

    pipe[3] = BrokenLog("alice", notices)
    loop = asyncio.get_running_loop()
    start = loop.time()

    with pytest.raises(RuntimeError, match="log bug"):
        await asyncio.wait_for(run_pipe(*pipe), 10)

    assert loop.time() - start < 1
    ffmpeg, streamlink = spawned
    assert ffmpeg.returncode == -signal.SIGKILL
    assert streamlink.returncode == -signal.SIGKILL


async def test_second_cancel_kills_both(
    pipe, spawned, blocking_streamlink, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_LINGER", "1")
    task = asyncio.create_task(run_pipe(*pipe))
    await wait_for_glob(tmp_path, blocking_streamlink.name)

    task.cancel()  # streamlink stops; FFmpeg read its input but never exits
    ffmpeg, streamlink = spawned
    await _wait_exited(streamlink)
    assert not task.done()
    loop = asyncio.get_running_loop()
    start = loop.time()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 10)

    assert loop.time() - start < 1
    assert streamlink.returncode == -signal.SIGTERM
    assert ffmpeg.returncode == -signal.SIGKILL
    assert (tmp_path / "rec.mp4.stdin").read_bytes() == b"fake ts data"


async def test_cancel_after_ffmpeg_exited_does_not_wait_out_the_grace(
    pipe, spawned, blocking_streamlink, monkeypatch, tmp_path
):
    monkeypatch.setattr(twitch_pipe, "STREAMLINK_TERM_GRACE", 5)
    monkeypatch.setenv("FAKE_STREAMLINK_IGNORE_TERM", "1")
    monkeypatch.setenv("FAKE_FFMPEG_SKIP_STDIN", "1")
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1")
    # Exiting before streamlink is ready would SIGTERM it before it ignores SIGTERM.
    monkeypatch.setenv("FAKE_FFMPEG_WAIT_FOR", str(blocking_streamlink))
    task = asyncio.create_task(run_pipe(*pipe))
    await wait_for_glob(tmp_path, blocking_streamlink.name)
    ffmpeg, streamlink = spawned
    await _wait_exited(ffmpeg)

    loop = asyncio.get_running_loop()
    start = loop.time()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 10)

    assert loop.time() - start < 1
    assert ffmpeg.returncode == 1
    assert streamlink.returncode == -signal.SIGKILL
