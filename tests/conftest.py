"""Shared test fixtures."""

import logging

import pytest

from streamdl import log_setup


@pytest.fixture(autouse=True)
def _reset_streamdl_logging():
    """Undo logging changes so every test starts with a clean 'streamdl' logger."""
    yield
    logger = logging.getLogger(log_setup.LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.NOTSET)
    log_setup.console_summary = None
