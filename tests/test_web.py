import asyncio
import logging
import signal
import socket

from fastapi.testclient import TestClient

from streamdl.web import WebServer, create_app


def test_health():
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.text == "OK"


def test_docs_are_disabled():
    assert TestClient(create_app()).get("/docs").status_code == 404


def test_uvicorn_installs_no_log_handlers_of_its_own():
    WebServer(create_app(), host="127.0.0.1", port=0)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        assert logging.getLogger(name).handlers == []
    assert logging.getLogger("uvicorn.error").propagate


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def test_server_serves_and_stops_without_touching_signals():
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    port = _free_port()
    server = WebServer(create_app(), host="127.0.0.1", port=port)
    task = asyncio.create_task(server.serve())
    for _ in range(250):
        if server.started:
            break
        await asyncio.sleep(0.02)
    assert {sig: signal.getsignal(sig) for sig in before} == before

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: test\r\nConnection: close\r\n\r\n")
    await writer.drain()
    body = await reader.read()
    writer.close()
    assert b" 200 OK" in body
    assert body.endswith(b"OK")

    server.should_exit = True
    await asyncio.wait_for(task, 5)


def test_health_answers_head():
    response = TestClient(create_app()).head("/health")
    assert response.status_code == 200
    assert response.content == b""
