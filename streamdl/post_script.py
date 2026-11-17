"""Run the user's post-download hook."""

from __future__ import annotations

import asyncio
import logging
import os

from .process import describe_exit, kill_process_group

log = logging.getLogger(__name__)


class PostScriptError(Exception):
    pass


async def run_post_script(
    script_path: str,
    file_path: str,
    user: str,
    site: str,
    dl_type: str,
    *,
    timeout: float,
) -> None:
    """Run script_path with the downloaded file as its first argument.

    Context is passed in STREAMDL_FILE, STREAMDL_USER, STREAMDL_SITE and STREAMDL_TYPE.
    The script runs in its own process group, which is killed if it outlives timeout.
    An empty script_path means no hook is configured.
    """
    if not script_path:
        return
    try:
        mode = os.stat(script_path).st_mode
    except OSError as e:
        raise PostScriptError(f"post_script not found: {e}") from e
    if mode & 0o111 == 0:
        raise PostScriptError(f"post_script {script_path} is not executable")

    log.info("Running post_script %s for %s (%s)", script_path, user, file_path)
    env = {
        **os.environ,
        "STREAMDL_FILE": file_path,
        "STREAMDL_USER": user,
        "STREAMDL_SITE": site,
        "STREAMDL_TYPE": dl_type,
    }
    try:
        proc = await asyncio.create_subprocess_exec(
            script_path,
            file_path,
            stdin=asyncio.subprocess.DEVNULL,
            env=env,
            process_group=0,
        )
    except OSError as e:
        raise PostScriptError(f"post_script {script_path} failed: {e}") from e
    try:
        returncode = await asyncio.wait_for(proc.wait(), timeout)
    except TimeoutError:
        await _kill(proc)
        raise PostScriptError(
            f"post_script {script_path} failed: timed out after {timeout:g}s"
        ) from None
    except BaseException:
        await _kill(proc)  # e.g. cancelled: don't leave the hook running
        raise
    if returncode != 0:
        raise PostScriptError(
            f"post_script {script_path} failed: {describe_exit(returncode)}"
        )
    log.info("post_script %s completed for %s", script_path, user)


async def _kill(proc: asyncio.subprocess.Process) -> None:
    """Kill a still-running hook's process group and reap the leader.

    The wait is shielded so a cancelled caller still reaps the leader.
    """
    if proc.returncode is None:
        kill_process_group(proc.pid)
    await asyncio.shield(proc.wait())
