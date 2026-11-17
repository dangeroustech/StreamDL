import io
import logging

import pytest

from streamdl import log_setup
from streamdl.progress import (
    DownloadKind,
    DownloadProgress,
    FfmpegLogWriter,
    ProgressSample,
    ProgressStore,
    format_bytes,
    format_download_progress,
    format_duration_short,
    log_active_download_summary,
    parse_ffmpeg_progress_line,
    progress_key_live,
    progress_key_vod,
)

KIB = 1024
MIB = 1024 * 1024


def test_status_line():
    s = parse_ffmpeg_progress_line(
        "frame= 1234 fps= 30 q=28.0 size=    1024kB time=00:00:41.20 bitrate= 203.4kbits/s speed=1.01x"
    )
    assert s.valid
    assert s.size_bytes == 1024 * KIB
    assert s.duration == pytest.approx(41.2)
    assert s.speed == pytest.approx(1.01)
    assert s.bitrate_kbps == pytest.approx(203.4)


def test_carriage_return_style_line():
    s = parse_ffmpeg_progress_line(
        "frame=  100 fps=0.0 q=-1.0 size=     256kB time=00:00:03.20 bitrate= 655.4kbits/s speed=6.4x"
    )
    assert s.valid
    assert s.size_bytes == 256 * KIB
    assert s.duration == pytest.approx(3.2)


def test_na_values_ignored():
    s = parse_ffmpeg_progress_line(
        "frame=    0 fps=0.0 q=0.0 size=N/A time=00:00:00.00 bitrate=N/A speed=N/A"
    )
    assert s.size_bytes == 0
    assert s.speed == 0


def test_non_progress_line():
    assert not parse_ffmpeg_progress_line(
        "Input #0, hls, from 'https://example.com/index.m3u8':"
    ).valid


def test_lsize_is_not_size():
    assert not parse_ffmpeg_progress_line(
        "[out#0/mp4] video:1kB Lsize=     2048kB"
    ).valid


@pytest.mark.parametrize(
    "line,field,expected",
    [
        ("total_size=1048576", "size_bytes", 1048576),
        ("out_time_ms=41200000", "duration", 41.2),
        ("out_time_us=1500000", "duration", 1.5),
        ("out_time=00:01:02.50", "duration", 62.5),
        ("speed=0.95x", "speed", 0.95),
        ("bitrate=203.4kbits/s", "bitrate_kbps", 203.4),
    ],
)
def test_progress_key_values(line, field, expected):
    s = parse_ffmpeg_progress_line(line)
    assert s.valid
    assert getattr(s, field) == pytest.approx(expected)


def test_progress_marker_is_not_a_sample():
    assert not parse_ffmpeg_progress_line("progress=continue").valid
    assert not parse_ffmpeg_progress_line("speed=N/A").valid


def test_store_percent_and_eta():
    store = ProgressStore()
    key = progress_key_vod("alice", "v123")
    store.start(
        key,
        channel="alice",
        kind=DownloadKind.VOD,
        vod_id="v123",
        title="Cool Stream",
        total_duration=100,
    )
    store.update(
        key, ProgressSample(size_bytes=10 * MIB, duration=40, speed=2.0, valid=True)
    )
    p = store.get(key)
    assert p.percent == pytest.approx(40)
    assert p.eta == pytest.approx(30)
    store.end(key)
    assert store.get(key) is None


def test_update_keeps_previous_values_for_zero_fields():
    store = ProgressStore()
    key = progress_key_live("alice")
    store.start(key, channel="alice", kind=DownloadKind.LIVE)
    store.update(key, ProgressSample(size_bytes=100, duration=5, valid=True))
    store.update(key, ProgressSample(valid=True))
    p = store.get(key)
    assert (p.size_bytes, p.duration) == (100, 5)
    assert p.percent is None and p.eta is None


def test_get_returns_a_copy():
    store = ProgressStore()
    key = progress_key_live("alice")
    store.start(key, channel="alice", kind=DownloadKind.LIVE)
    store.get(key).size_bytes = 999
    assert store.get(key).size_bytes == 0


def test_snapshot_sorted():
    store = ProgressStore()
    store.start(progress_key_live("zack"), channel="zack", kind=DownloadKind.LIVE)
    store.start(progress_key_live("alice"), channel="alice", kind=DownloadKind.LIVE)
    store.start(
        progress_key_vod("alice", "9"),
        channel="alice",
        kind=DownloadKind.VOD,
        vod_id="9",
    )
    snap = store.snapshot()
    assert [(p.channel, p.kind) for p in snap] == [
        ("alice", DownloadKind.LIVE),
        ("alice", DownloadKind.VOD),
        ("zack", DownloadKind.LIVE),
    ]


def _live_store(channel="day9tv"):
    store = ProgressStore()
    key = progress_key_live(channel)
    store.start(key, channel=channel, kind=DownloadKind.LIVE)
    return store, key


def test_writer_parses_cr_separated_lines():
    store, key = _live_store()
    writer = FfmpegLogWriter(key, store, debug_interval=3600)
    writer.write(
        b"frame= 10 fps=30 size=   128kB time=00:00:01.00 bitrate=100.0kbits/s speed=1.00x\r"
        b"frame= 20 fps=30 size=   256kB time=00:00:02.00 bitrate=100.0kbits/s speed=1.00x\r"
    )
    p = store.get(key)
    assert p.size_bytes == 256 * KIB
    assert p.duration == pytest.approx(2.0)
    assert "size=" in writer.text()


def test_writer_joins_lines_split_across_writes():
    store, key = _live_store()
    writer = FfmpegLogWriter(key, store, debug_interval=3600)
    writer.write(b"frame= 1 size=  12")
    writer.write(b"8kB time=00:00:01.00 speed=1x\n")
    assert store.get(key).size_bytes == 128 * KIB


def test_writer_keeps_only_the_last_64k():
    store, key = _live_store()
    writer = FfmpegLogWriter(key, store)
    writer.write(b"x" * 70000 + b"\nEND\n")
    text = writer.text()
    assert len(text) <= 64 * 1024
    assert text.endswith("END\n")


def test_format_download_progress_vod():
    s = format_download_progress(
        DownloadProgress(
            key="vod:bob:v1",
            channel="bob",
            kind=DownloadKind.VOD,
            title="Highlights",
            size_bytes=800 * MIB,
            duration=20 * 60,
            speed=0.95,
            percent=45.0,
            eta=24 * 60,
        )
    )
    assert (
        s
        == '[bob] vod "Highlights" 45.0% size=800.0MiB time=20m00s speed=0.95x eta=24m00s'
    )


def test_format_download_progress_live_minimal():
    assert (
        format_download_progress(
            DownloadProgress(key="live:a", channel="a", kind=DownloadKind.LIVE)
        )
        == "[a] live"
    )


@pytest.mark.parametrize(
    "n,expected",
    [(512, "512B"), (2048, "2.0KiB"), (5 * MIB, "5.0MiB"), (3 * 1024**3, "3.00GiB")],
)
def test_format_bytes(n, expected):
    assert format_bytes(n) == expected


@pytest.mark.parametrize(
    "seconds,expected",
    [(0, "0s"), (59.4, "59s"), (59.5, "1m00s"), (3661, "1h01m01s"), (-5, "0s")],
)
def test_format_duration_short(seconds, expected):
    assert format_duration_short(seconds) == expected


def test_log_active_download_summary(caplog):
    store, key = _live_store("alice")
    store.update(key, ProgressSample(size_bytes=1024, duration=60, speed=1, valid=True))
    console = io.StringIO()
    log_setup.console_summary = console
    caplog.set_level(logging.DEBUG, logger="streamdl")
    log_active_download_summary(store)
    assert "Active Downloads:" in caplog.text
    assert "[alice] live" in caplog.text
    assert "[alice] live" in console.getvalue()


def test_console_summary_when_idle():
    console = io.StringIO()
    log_setup.console_summary = console
    log_active_download_summary(ProgressStore())
    assert console.getvalue() == "Active Downloads:\n  (none)\n"


def test_go_style_ints_only():
    assert not parse_ffmpeg_progress_line("total_size=1_000").valid
    assert not parse_ffmpeg_progress_line("total_size=١٢").valid
    assert not parse_ffmpeg_progress_line("speed=1_0x").valid
    assert parse_ffmpeg_progress_line("total_size=+12").size_bytes == 12


_HUGE = "9" * 400


@pytest.mark.parametrize(
    "chunks",
    [
        [f"frame= 1 size={_HUGE}kB time=00:00:01.00 speed=1x\n"],
        [f"frame= 1 size={'9' * 307}GB time=00:00:01.00\n"],
        [f"out_time_ms={_HUGE}\n"],
        [f"total_size={'9' * 5000}\n"],
        ["out_time=00:00:inf\n", "out_time=00:00:nan\n"],
        [f"out_time={_HUGE}:00:00\n"],
        ["out_time=00:00:01\n", "speed=1e-320x\n"],
        ["speed=1e400x\n", "bitrate=infkbits/s\n"],
    ],
)
def test_hostile_ffmpeg_output_never_raises(chunks, caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    store = ProgressStore()
    key = progress_key_vod("bob", "v1")
    store.start(
        key, channel="bob", kind=DownloadKind.VOD, vod_id="v1", total_duration=100
    )
    writer = FfmpegLogWriter(key, store, debug_interval=0)
    for chunk in chunks:
        writer.write(chunk.encode())
    line = format_download_progress(store.get(key))
    assert "inf" not in line and "nan" not in line
    console = io.StringIO()
    log_setup.console_summary = console
    log_active_download_summary(store)
    assert "[bob] vod" in console.getvalue()


def test_writer_debug_line_is_throttled(caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    store, key = _live_store()
    now = [0.0]
    writer = FfmpegLogWriter(key, store, debug_interval=10, clock=lambda: now[0])
    for t in (0.0, 5.0, 9.9, 10.0, 15.0, 20.5):
        now[0] = t
        writer.write(b"frame= 1 size=  128kB time=00:00:01.00 speed=1x\n")
    debug = [
        r for r in caplog.records if r.getMessage().startswith("download progress")
    ]
    assert len(debug) == 3  # at t=0, t=10 and t=20.5


def test_writer_skips_debug_formatting_when_debug_is_off(caplog, monkeypatch):
    def fail(_p):
        raise AssertionError("formatted a debug line with DEBUG off")

    monkeypatch.setattr("streamdl.progress.format_download_progress", fail)
    caplog.set_level(logging.INFO, logger="streamdl")
    store, key = _live_store()
    writer = FfmpegLogWriter(key, store, debug_interval=0)
    writer.write(b"frame= 1 size=  128kB time=00:00:01.00 speed=1x\n")
    assert store.get(key).size_bytes == 128 * KIB
    assert not caplog.records


def test_writer_caps_an_unterminated_line():
    store, key = _live_store()
    writer = FfmpegLogWriter(key, store)
    for _ in range(5):
        writer.write(b"x" * 50000)
    assert len(writer._partial) <= FfmpegLogWriter.MAX_BYTES
    writer.write(b"\nframe= 1 size=  128kB time=00:00:01.00 speed=1x\n")
    assert store.get(key).size_bytes == 128 * KIB
