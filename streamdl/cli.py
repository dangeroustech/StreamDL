"""Command-line entry point: parse flags, set up logging, run until SIGINT/SIGTERM."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import NoReturn

from .config import ConfigError, ConfigLoader, load_config
from .log_setup import LogDest, setup_logging
from .resolver import LibraryResolver
from .runtime import Runtime
from .scheduler import Scheduler
from .settings import Settings
from .web import WebServer, create_app

log = logging.getLogger("streamdl")

_GO_BOOLS = {
    **dict.fromkeys(("1", "t", "T", "TRUE", "true", "True"), True),
    **dict.fromkeys(("0", "f", "F", "FALSE", "false", "False"), False),
}


def _go_bool(value: str) -> bool:
    """A boolean flag value, accepting what Go's strconv.ParseBool accepts."""
    try:
        return _GO_BOOLS[value]
    except KeyError:
        raise argparse.ArgumentTypeError(f"invalid boolean value {value!r}") from None


def build_parser(env: Mapping[str, str]) -> argparse.ArgumentParser:
    """Flags keep their v3 single-dash spellings; double dashes work too.

    As with Go's flag package, values may follow '=' (-time=30) and the boolean
    flag also takes one that way (-subfolder=false).
    """
    parser = argparse.ArgumentParser(
        prog="streamdl",
        description="Monitor streaming sites and record live streams and VODs.",
        allow_abbrev=False,
        add_help=False,
    )

    def flag(name: str, **kwargs) -> None:
        parser.add_argument(f"-{name}", f"--{name}", **kwargs)

    parser.add_argument(
        "-h", "-help", "--help", action="help", help="show this help and exit"
    )
    flag("config", default="config.yml", help="config file path")
    flag("out", default="", help="folder for in-progress recordings")
    flag("move", default="", help="folder that finished recordings are moved to")
    flag("time", type=int, default=60, help="seconds between checks")
    flag(
        "batch",
        type=int,
        default=5,
        help="seconds between URL checks; raise if rate limited",
    )
    flag(
        "subfolder",
        type=_go_bool,
        nargs="?",
        const=True,
        default=False,
        metavar="BOOL",
        help="put recordings in a folder per channel",
    )
    flag(
        "log-level",
        default=env.get("LOG_LEVEL", "").strip() or "info",
        help="trace, debug, info, warn, error",
    )
    flag(
        "log-dest",
        default=env.get("LOG_DEST", "").strip() or "file",
        help="file, stdout or both",
    )
    flag(
        "log-file",
        default=env.get("LOG_FILE", ""),
        help="log file (default <data>/streamdl.log)",
    )
    flag(
        "data",
        default="/app/data",
        help="folder for the VOD database and default log file",
    )
    flag("vod-out", default="", help="in-progress folder for VODs (default: -out)")
    flag("vod-move", default="", help="finished folder for VODs (default: -move)")
    return parser


def main(
    argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None
) -> int:
    env = os.environ if env is None else env
    args = build_parser(env).parse_args(argv)
    try:
        logging_cfg = setup_logging(
            args.log_level, args.log_dest, args.log_file, args.data
        )
    except (ValueError, OSError) as e:
        print(f"Logging setup failed: {e}", file=sys.stderr)
        return 1
    try:
        # After logging setup, so warnings about bad env values reach the log.
        settings = Settings.from_args(args, env)
        if logging_cfg.dest is LogDest.STDOUT:
            log.info("Starting StreamDL... (dest: %s)", logging_cfg.dest)
        else:
            log.info(
                "Starting StreamDL... (log file: %s, dest: %s)",
                logging_cfg.file_path,
                logging_cfg.dest,
            )
        if env.get("STREAMDL_GRPC_ADDR") or env.get("STREAMDL_GRPC_PORT"):
            log.info(
                "STREAMDL_GRPC_ADDR/STREAMDL_GRPC_PORT are no longer used: StreamDL v4 "
                "runs in one container, so the separate server container can be removed."
            )
        try:
            initial = load_config(settings.config_path)
        except ConfigError as e:
            log.critical("Config Error: %s", e)
            return 1
        log.debug("Config: %s", initial)
        return asyncio.run(run(settings, ConfigLoader(settings.config_path, initial)))
    finally:
        logging_cfg.close()


async def run(settings: Settings, config: ConfigLoader) -> int:
    rt = Runtime(settings=settings, resolver=LibraryResolver())
    scheduler = Scheduler(rt, config)
    web = WebServer(create_app())
    stop = asyncio.Event()
    _install_signal_handlers(stop)
    web_task = asyncio.create_task(web.serve(), name="web")
    try:
        # Returns once stop is set and Scheduler.shutdown() has stopped recordings,
        # waited for post-scripts and closed the resolver and VOD database.
        await scheduler.run(stop)
    finally:
        web.should_exit = True
        await asyncio.gather(web_task, return_exceptions=True)
    log.info("StreamDL stopped")
    return 0


def _signal_handler(
    stop: asyncio.Event, exit_now: Callable[[int], NoReturn] = os._exit
) -> Callable[[int], None]:
    """First signal: shut down cleanly. Second: exit at once, skipping cleanup."""

    def handle(signum: int) -> None:
        if stop.is_set():
            log.warning("Second signal received; exiting immediately")
            exit_now(1)
        log.info("Received %s; shutting down...", signal.Signals(signum).name)
        stop.set()

    return handle


def _install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    handle = _signal_handler(stop)
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, handle, signum)
