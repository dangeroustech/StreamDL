import argparse
import logging
from pathlib import Path

import pytest

from streamdl.settings import FfmpegOptions, Settings, env_int, split_args


def test_env_int():
    assert env_int({}, "X", 3) == 3
    assert env_int({"X": ""}, "X", 3) == 3
    assert env_int({"X": " 7 "}, "X", 3) == 7


def test_env_int_invalid_warns(caplog):
    caplog.set_level(logging.WARNING, logger="streamdl")
    assert env_int({"X": "abc"}, "X", 3) == 3
    assert "Invalid X value 'abc'" in caplog.text


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", []),
        ("-t 15", ["-t", "15"]),
        ("  -t   15  ", ["-t", "15"]),
        ('-headers "X-Test: a b" -t 15', ["-headers", "X-Test: a b", "-t", "15"]),
        ("-metadata 'title=a \"b\"'", ["-metadata", 'title=a "b"']),
        ('a""b', ["ab"]),
    ],
)
def test_split_args(raw, expected):
    assert split_args(raw) == expected


def test_ffmpeg_defaults():
    opts = FfmpegOptions.from_env({})
    assert opts == FfmpegOptions()
    assert opts.rw_timeout_us == "15000000"
    assert opts.reconnect is True
    assert opts.reconnect_delay_max == "15"
    assert opts.stream_copy is False
    assert opts.max_retries == 3
    assert opts.retry_base_delay == 2.0


def test_ffmpeg_from_env():
    opts = FfmpegOptions.from_env(
        {
            "FFMPEG_RW_TIMEOUT_US": "5000000",
            "FFMPEG_PROTOCOL_WHITELIST": " file,http ",
            "FFMPEG_USER_AGENT": "UA 1",
            "FFMPEG_RECONNECT_DELAY_MAX": "7",
            "FFMPEG_STREAM_COPY": "true",
            "FFMPEG_EXTRA_INPUT_OPTS": '-headers "X: y"',
            "FFMPEG_EXTRA_OUTPUT_OPTS": "-t 15",
            "FFMPEG_MAX_RETRIES": "5",
            "FFMPEG_RETRY_BASE_DELAY_SECONDS": "1",
        }
    )
    assert opts.rw_timeout_us == "5000000"
    assert opts.protocol_whitelist == "file,http"
    assert opts.user_agent == "UA 1"
    assert opts.reconnect_delay_max == "7"
    assert opts.stream_copy is True
    assert opts.extra_input == ("-headers", "X: y")
    assert opts.extra_output == ("-t", "15")
    assert opts.max_retries == 5
    assert opts.retry_base_delay == 1.0


@pytest.mark.parametrize("value", ["0", "false", "FALSE"])
def test_reconnect_disabled(value):
    assert FfmpegOptions.from_env({"FFMPEG_RECONNECT": value}).reconnect is False


@pytest.mark.parametrize("value", ["1", "true", " TRUE "])
def test_stream_copy_enabled(value):
    assert FfmpegOptions.from_env({"FFMPEG_STREAM_COPY": value}).stream_copy is True


def test_stream_copy_other_values_are_off():
    assert FfmpegOptions.from_env({"FFMPEG_STREAM_COPY": "yes"}).stream_copy is False


def _args(**overrides):
    values = dict(
        config="config.yml",
        out="/dl",
        move="/out",
        time=60,
        batch=5,
        subfolder=False,
        data="/app/data",
        vod_out="",
        vod_move="",
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def test_settings_vod_dirs_default_to_live_dirs():
    s = Settings.from_args(_args(), {})
    assert s.config_path == Path("config.yml")
    assert (s.vod_out_dir, s.vod_move_dir) == ("/dl", "/out")
    assert s.post_script_timeout == 1800
    assert s.ffmpeg == FfmpegOptions()


def test_settings_explicit_values():
    s = Settings.from_args(
        _args(vod_out="/vdl", vod_move="/vout", time=30, batch=1, subfolder=True),
        {"STREAMDL_POST_SCRIPT_TIMEOUT": "60", "FFMPEG_MAX_RETRIES": "5"},
    )
    assert (s.vod_out_dir, s.vod_move_dir) == ("/vdl", "/vout")
    assert (s.tick_seconds, s.batch_seconds, s.subfolder) == (30, 1, True)
    assert s.post_script_timeout == 60
    assert s.ffmpeg.max_retries == 5
