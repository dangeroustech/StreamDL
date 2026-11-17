import json
from pathlib import Path

import pytest

from streamdl.ffmpeg import (
    build_live_args,
    build_vod_args,
    sanitize_args,
    sanitize_log,
    tail_lines,
)
from streamdl.settings import FfmpegOptions

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "ffmpeg_args.json").read_text()
)["cases"]


def test_fixture_count():
    assert len(FIXTURES) == 8


@pytest.mark.parametrize("case", FIXTURES, ids=lambda c: c["name"])
def test_matches_v3_client(case):
    opts = FfmpegOptions.from_env(case["env"] or {})
    if case["kind"] == "live":
        got = build_live_args(case["video"], case["audio"], "<OUT>", opts)
    else:
        got = build_vod_args(case["video"], "<OUT>")
    assert got == case["args"]


def test_uses_the_given_ffmpeg_path():
    args = build_live_args(
        "v", "", "out.mp4", FfmpegOptions(), ffmpeg="/usr/local/bin/ffmpeg"
    )
    assert args[0] == "/usr/local/bin/ffmpeg"
    assert build_vod_args("v", "out.mp4", ffmpeg="/x/ffmpeg")[0] == "/x/ffmpeg"


def test_sanitize_args():
    args = [
        "ffmpeg",
        "-user_agent",
        "UA",
        "-i",
        "https://x/a.m3u8?token=1",
        "-f",
        "mp4",
        "out.mp4",
    ]
    assert (
        sanitize_args(args)
        == "ffmpeg -user_agent <redacted> -i <redacted> -f mp4 out.mp4"
    )


def test_sanitize_log():
    line = "GET https://x/a.m3u8?token=abc&sig=def&p=1"
    assert (
        sanitize_log(line) == "GET https://x/a.m3u8?token=<redacted>&sig=<redacted>&p=1"
    )


def test_sanitize_log_token_at_end():
    assert sanitize_log("url?token=abc") == "url?token=<redacted>"


def test_tail_lines():
    assert tail_lines("a\nb\nc", 2) == "b\nc"
    assert tail_lines("a\nb", 5) == "a\nb"
    assert tail_lines("", 3) == ""
    assert tail_lines("a", 0) == ""


def test_sanitize_log_redacts_every_occurrence_per_line():
    tail = (
        "Opening 'https://x/a.m3u8?sig=s1&token=t1&p=1' for reading\n"
        "GET https://x/b.m3u8?token=t2\n"
        "retrying https://x/c.m3u8?lsig=l3&signature=s4 now\n"
        "next line & stays"
    )
    assert sanitize_log(tail) == (
        "Opening 'https://x/a.m3u8?sig=<redacted>&token=<redacted>&p=1' for reading\n"
        "GET https://x/b.m3u8?token=<redacted>\n"
        "retrying https://x/c.m3u8?lsig=<redacted>&signature=<redacted> now\n"
        "next line & stays"
    )
