"""Shared test fixtures."""

import logging

import pytest

from streamdl import log_setup


def _unsilence_streamdl_loggers():
    # The old gRPC server module (imported by the old server tests) sets every logger
    # that exists at import time to CRITICAL with propagate=False. Undo that for ours.
    # Remove this once the old server tests are deleted.
    prefix = log_setup.LOGGER_NAME + "."
    for name in list(logging.root.manager.loggerDict):
        if name == log_setup.LOGGER_NAME or name.startswith(prefix):
            logger = logging.getLogger(name)
            logger.setLevel(logging.NOTSET)
            logger.propagate = True


@pytest.fixture(autouse=True)
def _reset_streamdl_logging():
    """Undo logging changes so every test starts with a clean 'streamdl' logger."""
    _unsilence_streamdl_loggers()
    yield
    logger = logging.getLogger(log_setup.LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.NOTSET)
    log_setup.console_summary = None
