"""Shared test fixtures."""

import logging

import pytest
from helpers import FAKE_FFMPEG, FakeResolver, FakeSleep

from streamdl import log_setup
from streamdl.runtime import Runtime
from streamdl.settings import Settings, TwitchOptions


@pytest.fixture(autouse=True)
def _reset_streamdl_logging():
    """Undo logging changes so every test starts with clean logging."""
    yield
    root = logging.getLogger()
    for handler in log_setup._installed:
        root.removeHandler(handler)
        handler.close()
    log_setup._installed.clear()
    logging.captureWarnings(False)
    logging.getLogger(log_setup.LOGGER_NAME).setLevel(logging.NOTSET)
    log_setup.console_summary = None
    log_setup._summary_owner = None


@pytest.fixture
def ffmpeg_log(tmp_path, monkeypatch):
    path = tmp_path / "ffmpeg-runs.jsonl"
    monkeypatch.setenv("FAKE_FFMPEG_LOG", str(path))
    return path


@pytest.fixture
def make_runtime(tmp_path, ffmpeg_log):
    """Build a Runtime wired to the fake ffmpeg, a FakeResolver and a FakeSleep."""

    def make(**overrides):
        values = dict(
            config_path=tmp_path / "config.yml",
            out_dir=str(tmp_path / "dl"),
            move_dir=str(tmp_path / "out"),
            vod_out_dir=str(tmp_path / "dl"),
            vod_move_dir=str(tmp_path / "out"),
            data_dir=str(tmp_path / "data"),
            ffmpeg_path=FAKE_FFMPEG,
            # Recorder tests take the direct FFmpeg path unless they opt in.
            twitch=TwitchOptions(adfree=False),
        )
        values.update(overrides)
        return Runtime(
            settings=Settings(**values), resolver=FakeResolver(), sleep=FakeSleep()
        )

    return make
