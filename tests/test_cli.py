import asyncio
import logging
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from streamdl import cli
from streamdl.cli import _signal_handler, build_parser, main


def test_flags_accept_single_and_double_dashes():
    args = build_parser({}).parse_args(
        [
            "-config",
            "/c.yml",
            "--out",
            "/dl",
            "-time",
            "30",
            "-subfolder",
            "--log-level",
            "debug",
            "-vod-out",
            "/v",
        ]
    )
    assert (
        args.config,
        args.out,
        args.time,
        args.subfolder,
        args.log_level,
        args.vod_out,
    ) == (
        "/c.yml",
        "/dl",
        30,
        True,
        "debug",
        "/v",
    )


def test_flags_accept_go_style_equals_values():
    args = build_parser({}).parse_args(
        ["-config=/c.yml", "--batch=7", "-log-dest=both"]
    )
    assert (args.config, args.batch, args.log_dest) == ("/c.yml", 7, "both")


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["-subfolder"], True),
        (["-subfolder=true"], True),
        (["--subfolder=1"], True),
        (["-subfolder=T"], True),
        (["-subfolder=false"], False),
        (["-subfolder=0"], False),
        (["-subfolder=F"], False),
        (["-subfolder", "-time", "5"], True),
    ],
)
def test_subfolder_takes_go_boolean_values(argv, expected):
    assert build_parser({}).parse_args(argv).subfolder is expected


def test_bad_boolean_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        build_parser({}).parse_args(["-subfolder=maybe"])
    assert exc.value.code == 2


@pytest.mark.parametrize("flag", ["-h", "-help", "--help"])
def test_help_flags(flag, capsys):
    with pytest.raises(SystemExit) as exc:
        build_parser({}).parse_args([flag])
    assert exc.value.code == 0
    assert "-log-dest" in capsys.readouterr().out


def test_defaults():
    args = build_parser({}).parse_args([])
    assert args.config == "config.yml"
    assert (args.out, args.move, args.vod_out, args.vod_move) == ("", "", "", "")
    assert (args.time, args.batch, args.subfolder) == (60, 5, False)
    assert (args.log_level, args.log_dest, args.log_file) == ("info", "file", "")
    assert args.data == "/app/data"


def test_logging_defaults_come_from_env():
    args = build_parser(
        {"LOG_LEVEL": "debug", "LOG_DEST": "stdout", "LOG_FILE": "/x.log"}
    ).parse_args([])
    assert (args.log_level, args.log_dest, args.log_file) == (
        "debug",
        "stdout",
        "/x.log",
    )


def test_blank_logging_env_means_the_default():
    args = build_parser({"LOG_LEVEL": "  ", "LOG_DEST": " "}).parse_args([])
    assert (args.log_level, args.log_dest) == ("info", "file")


def test_missing_config_exits_1(tmp_path, caplog):
    argv = [
        "-config",
        str(tmp_path / "nope.yml"),
        "-log-dest",
        "stdout",
        "-data",
        str(tmp_path),
    ]
    assert main(argv, env={}) == 1
    assert "Config Error: cannot read" in caplog.text


def test_bad_log_dest_exits_1(capsys):
    assert main(["-log-dest", "nope"], env={}) == 1
    assert "Logging setup failed" in capsys.readouterr().err


@pytest.mark.parametrize(
    "env", [{"STREAMDL_GRPC_ADDR": "server"}, {"STREAMDL_GRPC_PORT": "50051"}]
)
def test_grpc_env_logs_an_upgrade_hint(env, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="streamdl")
    argv = [
        "-config",
        str(tmp_path / "nope.yml"),
        "-log-dest",
        "stdout",
        "-data",
        str(tmp_path),
    ]
    main(argv, env=env)
    assert any(
        r.levelno == logging.INFO and "no longer used" in r.getMessage()
        for r in caplog.records
    )


def _get(url, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return response.read().decode()
        except urllib.error.URLError, ConnectionError:
            time.sleep(0.2)
    raise AssertionError(f"{url} never answered")


def test_runs_serves_health_and_stops_on_sigterm(tmp_path):
    config = tmp_path / "config.yml"
    config.write_text("[]\n")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamdl",
            "-config",
            str(config),
            "-log-dest",
            "stdout",
            "-data",
            str(tmp_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert _get("http://127.0.0.1:8080/health", 20) == "OK"
        proc.send_signal(signal.SIGTERM)
        output, _ = proc.communicate(timeout=15)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 0, output
    assert "Running StreamDL at" in output
    assert "StreamDL stopped" in output


def test_second_signal_exits_immediately():
    stop = asyncio.Event()
    exits = []
    handle = _signal_handler(stop, exit_now=exits.append)
    handle(signal.SIGTERM)
    assert stop.is_set() and exits == []
    handle(signal.SIGINT)
    assert exits == [1]


@pytest.mark.parametrize(
    "argv,error",
    [
        (["-time", "0"], "argument -time/--time: must be greater than 0"),
        (["-time=-5"], "argument -time/--time: must be greater than 0"),
        (["-batch", "-1"], "argument -batch/--batch: must not be negative"),
        (["-time", "x"], "argument -time/--time: invalid integer value 'x'"),
    ],
)
def test_bad_intervals_are_usage_errors(argv, error, capsys):
    with pytest.raises(SystemExit) as exc:
        build_parser({}).parse_args(argv)
    assert exc.value.code == 2
    assert error in capsys.readouterr().err


def test_batch_zero_is_allowed():
    assert build_parser({}).parse_args(["-batch", "0"]).batch == 0


def test_web_server_startup_failure_exits_1(tmp_path):
    config = tmp_path / "config.yml"
    config.write_text("[]\n")
    with socket.socket() as blocker:
        blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        blocker.bind(("0.0.0.0", 8080))
        blocker.listen()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "streamdl",
                "-config",
                str(config),
                "-log-dest",
                "stdout",
                "-data",
                str(tmp_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
    assert result.returncode == 1, result.stdout
    assert re.search(r"\] ERROR .*address already in use", result.stdout)
    assert "CRITICAL Web server could not start; stopping" in result.stdout


def test_first_signal_after_a_web_failure_still_shuts_down_cleanly():
    stop = asyncio.Event()
    stop.set()  # what _serve_web does when the server can't start
    exits = []
    handle = _signal_handler(stop, exit_now=exits.append)
    handle(signal.SIGTERM)
    assert exits == []
    handle(signal.SIGTERM)
    assert exits == [1]


def test_unexpected_failure_is_logged_to_the_log_file(tmp_path, monkeypatch):
    async def failing_run(settings, config):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "run", failing_run)
    # Leftover resolver threads from other tests must not end the test run.
    monkeypatch.setattr(cli, "_exit_if_lookups_running", lambda rc: None)
    config = tmp_path / "config.yml"
    config.write_text("[]\n")
    argv = ["-config", str(config), "-log-dest", "file", "-data", str(tmp_path)]
    assert main(argv, env={}) == 1
    text = (tmp_path / "streamdl.log").read_text()
    assert "CRITICAL StreamDL failed: boom" in text
    assert "RuntimeError: boom" in text  # the traceback


# Run as a script: the lookup blocks forever, as a hung streamlink call can.
_HUNG_LOOKUP = """
import pathlib, sys, threading
import streamdl.resolver

def hung(*args, **kwargs):
    pathlib.Path(sys.argv[1]).touch()
    threading.Event().wait()

streamdl.resolver.get_stream = hung
from streamdl.cli import main
raise SystemExit(main(sys.argv[2:]))
"""


def test_exits_promptly_while_a_lookup_thread_is_still_running(tmp_path):
    config = tmp_path / "config.yml"
    config.write_text("- site: twitch.tv\n  channels:\n  - name: someone\n")
    marker = tmp_path / "lookup-started"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _HUNG_LOOKUP,
            str(marker),
            "-config",
            str(config),
            "-log-dest",
            "stdout",
            "-data",
            str(tmp_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while not marker.exists():
            assert time.monotonic() < deadline, "lookup never started"
            time.sleep(0.1)
        proc.send_signal(signal.SIGTERM)
        output, _ = proc.communicate(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 0, output
    assert "StreamDL stopped" in output
