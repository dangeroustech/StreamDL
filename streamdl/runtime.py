"""State shared by the scheduler and the recording tasks."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .notices import NoticeBuffer
from .post_script import PostScriptError, run_post_script
from .progress import ProgressStore
from .settings import Settings

if TYPE_CHECKING:
    from .resolver import Resolver

log = logging.getLogger(__name__)


@dataclass
class Runtime:
    settings: Settings
    resolver: Resolver
    progress: ProgressStore = field(default_factory=ProgressStore)
    notices: NoticeBuffer = field(default_factory=NoticeBuffer)
    active: set[str] = field(default_factory=set)  # live channels being recorded
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep  # replaced in tests
    _site_locks: dict[str, asyncio.Lock] = field(default_factory=dict)
    _post_scripts: set[asyncio.Task[None]] = field(default_factory=set)

    def site_lock(self, site: str) -> asyncio.Lock:
        """One lock per site, so lookups for a site don't hit its API at the same time."""
        if site not in self._site_locks:
            self._site_locks[site] = asyncio.Lock()
        return self._site_locks[site]

    def spawn_post_script(
        self,
        script: str,
        file_path: str,
        user: str,
        site: str,
        dl_type: str,
        *,
        label: str = "",
    ) -> None:
        """Run the hook in the background; failures are logged as
        "post_script failed for <label or user>"."""
        if not script:
            return
        task = asyncio.create_task(
            self._run_post_script(script, file_path, user, site, dl_type, label or user)
        )
        self._post_scripts.add(task)
        task.add_done_callback(self._post_scripts.discard)

    async def wait_for_post_scripts(self) -> None:
        """Wait for every running hook, including any spawned while waiting."""
        while self._post_scripts:
            await asyncio.gather(*list(self._post_scripts), return_exceptions=True)

    async def _run_post_script(
        self,
        script: str,
        file_path: str,
        user: str,
        site: str,
        dl_type: str,
        label: str,
    ) -> None:
        try:
            await run_post_script(
                script,
                file_path,
                user,
                site,
                dl_type,
                timeout=self.settings.post_script_timeout,
            )
        except PostScriptError as e:
            log.error("post_script failed for %s: %s", label, e)
        except Exception:
            log.exception("post_script failed for %s", label)
