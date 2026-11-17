import logging

import pytest
from ruamel.yaml import YAML

from streamdl.config import ConfigError, ConfigLoader, load_config, parse_config


def test_vod_fields():
    sites = parse_config("""
- site: twitch.tv
  channels:
  - name: testuser
    quality: best
    vod: true
    vod_limit: 5
- site: twitch.tv
  channels:
  - name: liveuser
    quality: best
""")
    assert len(sites) == 2
    vod = sites[0].channels[0]
    assert vod.vod is True
    assert vod.vod_limit == 5
    assert vod.effective_vod_limit == 5
    live = sites[1].channels[0]
    assert live.vod is False
    assert live.vod_limit == 0
    assert live.effective_vod_limit == 10


def test_post_script():
    sites = parse_config("""
- site: twitch.tv
  post_script: /scripts/transcode.sh
  channels:
  - name: testuser
    quality: best
- site: youtube.com
  channels:
  - name: otheruser
    quality: best
""")
    assert sites[0].post_script == "/scripts/transcode.sh"
    assert sites[1].post_script == ""


def test_loose_input_like_v3():
    sites = parse_config("""
- site: twitch.tv
  unknown_key: ignored
  channels:
  - name: 12345
    extra: ignored
  - name: other
    quality: 720
""")
    first, second = sites[0].channels
    assert first.name == "12345"
    assert first.quality == ""
    assert second.quality == "720"


def test_null_values_use_defaults():
    sites = parse_config("- site: kick.com\n  post_script:\n  channels:\n")
    assert sites[0].channels == []
    assert sites[0].post_script == ""


def test_yaml_1_2_words_stay_strings():
    sites = parse_config(
        "- site: twitch.tv\n  channels:\n  - name: off\n    quality: no\n"
    )
    channel = sites[0].channels[0]
    assert channel.name == "off"
    assert channel.quality == "no"


@pytest.mark.parametrize(
    "field,text",
    [
        ("name", "true"),
        ("name", "0x1F"),
        ("name", "2024-01-01"),
        ("name", "007"),
        ("quality", "1.50"),
    ],
)
def test_scalars_keep_their_source_text(field, text):
    sites = parse_config(f"- site: twitch.tv\n  channels:\n  - {field}: {text}\n")
    assert getattr(sites[0].channels[0], field) == text


@pytest.mark.parametrize("text", ["true", "yes", "True"])
def test_vod_bool_words(text):
    sites = parse_config(f"- site: twitch.tv\n  channels:\n  - vod: {text}\n")
    assert sites[0].channels[0].vod is True


def test_global_safe_constructor_is_untouched():
    assert YAML(typ="safe", pure=True).load("a: 1\nb: true\n") == {"a": 1, "b": True}


def test_empty_file_is_empty_config():
    assert parse_config("") == []


def test_channels_must_be_a_list():
    with pytest.raises(ConfigError):
        parse_config("- site: test.example\n  channels: true\n")


def test_top_level_must_be_a_list():
    with pytest.raises(ConfigError):
        parse_config("site: twitch.tv\n")


def test_invalid_yaml():
    with pytest.raises(ConfigError):
        parse_config("- site: [unclosed\n")


def test_load_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yml")


def test_loader_keeps_last_good_config(tmp_path, caplog):
    path = tmp_path / "config.yml"
    path.write_text("- site: twitch.tv\n  channels:\n  - name: alice\n")
    loader = ConfigLoader(path, load_config(path))

    path.write_text("- site: twitch.tv\n  channels: true\n")
    with caplog.at_level(logging.WARNING, logger="streamdl"):
        sites = loader.reload()
    assert sites[0].channels[0].name == "alice"
    assert "keeping previous config" in caplog.text

    path.write_text("- site: kick.com\n  channels: []\n")
    assert loader.reload()[0].site == "kick.com"
