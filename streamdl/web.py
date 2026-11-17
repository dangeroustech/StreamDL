"""HTTP server: /health for now; the management API arrives in phase 3."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

ALL_INTERFACES = (
    "0.0.0.0"  # nosec B104 - runs in a container; compose decides what's published
)
DEFAULT_PORT = 8080


def create_app() -> FastAPI:
    app = FastAPI(title="StreamDL", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health", response_class=PlainTextResponse)
    async def health() -> str:
        return "OK"

    return app


class WebServer(uvicorn.Server):
    """uvicorn server that leaves signal handling to StreamDL's own shutdown logic.

    log_config=None stops uvicorn installing its own handlers and format; its
    loggers propagate to StreamDL's handlers instead.
    """

    def __init__(
        self, app: FastAPI, host: str = ALL_INTERFACES, port: int = DEFAULT_PORT
    ) -> None:
        super().__init__(
            uvicorn.Config(
                app,
                host=host,
                port=port,
                log_config=None,
                log_level="warning",
                access_log=False,
                lifespan="off",
            )
        )

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield
