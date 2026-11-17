"""config.yml models and loading."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
)
from ruamel.yaml import YAML
from ruamel.yaml.constructor import SafeConstructor
from ruamel.yaml.error import YAMLError

log = logging.getLogger(__name__)

DEFAULT_VOD_LIMIT = 10


class ConfigError(Exception):
    """The config file could not be read or parsed."""


class _RawScalars(SafeConstructor):
    """Keeps bool/int/float/timestamp scalars as their source text, like yaml.v3.

    `name: 007` stays "007" and `name: true` stays "true"; pydantic converts the text
    for typed fields (`vod: yes` -> True, `vod_limit: 5` -> 5). Nulls are untouched.
    """


for _tag in ("bool", "int", "float", "timestamp"):
    # add_constructor copies the table first, so SafeConstructor itself is unchanged
    _RawScalars.add_constructor(
        f"tag:yaml.org,2002:{_tag}", SafeConstructor.construct_scalar
    )


class _Model(BaseModel):
    # Decode as loosely as the v3 client did: unknown keys are ignored.
    model_config = ConfigDict(extra="ignore")

    @field_validator("*", mode="before")
    @classmethod
    def _null_means_default(cls, value: Any, info: ValidationInfo) -> Any:
        # yaml.v3 decoded `key:` (null) to the zero value; do the same
        if value is None:
            return cls.model_fields[info.field_name].get_default(
                call_default_factory=True
            )
        return value


class Channel(_Model):
    name: str = ""
    quality: str = ""
    vod: bool = False
    vod_limit: int = 0

    @property
    def effective_vod_limit(self) -> int:
        return self.vod_limit if self.vod_limit > 0 else DEFAULT_VOD_LIMIT


class Site(_Model):
    site: str = ""
    post_script: str = ""
    channels: list[Channel] = Field(default_factory=list)


def parse_config(data: str | bytes) -> list[Site]:
    """Parse config.yml content into sites; raises ConfigError."""
    try:
        text = data.decode("utf-8") if isinstance(data, bytes) else data
        yaml = YAML(typ="safe", pure=True)
        yaml.Constructor = _RawScalars
        raw = yaml.load(text)
    except (UnicodeDecodeError, YAMLError) as e:
        raise ConfigError(f"invalid YAML: {e}") from e
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ConfigError("config must be a list of sites")
    try:
        return [Site.model_validate(item) for item in raw]
    except ValidationError as e:
        raise ConfigError(str(e)) from e


def load_config(path: Path) -> list[Site]:
    try:
        data = path.read_bytes()
    except OSError as e:
        raise ConfigError(f"cannot read {path}: {e}") from e
    return parse_config(data)


class ConfigLoader:
    """Re-reads the config every round, keeping the last good version if a reload fails."""

    def __init__(self, path: Path, initial: list[Site]) -> None:
        self.path = path
        self.current = initial

    def reload(self) -> list[Site]:
        try:
            self.current = load_config(self.path)
        except ConfigError as e:
            log.warning("Config reload failed; keeping previous config: %s", e)
        return self.current
