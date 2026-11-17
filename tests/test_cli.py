import asyncio
import logging
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

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


def test_missing_config_exits_1(tmp_path):
    argv = [
        "-config",
        str(tmp_path / "nope.yml"),
        "-log-dest",
        "stdout",
        "-data",
        str(tmp_path),
    ]
    assert main(argv, env={}) == 1


def test_bad_log_dest_exits_1(capsys):
    assert main(["-log-dest", "nope"], env={}) == 1
    assert "Logging setup failed" in capsys.readouterr().err


def test_grpc_env_logs_an_upgrade_hint(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="streamdl")
    argv = [
        "-config",
        str(tmp_path / "nope.yml"),
        "-log-dest",
        "stdout",
        "-data",
        str(tmp_path),
    ]
    main(argv, env={"STREAMDL_GRPC_ADDR": "server"})
    assert "no longer used" in caplog.text


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
