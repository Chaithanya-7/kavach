import pytest

from endpoint_framework.core.config import ConfigError, FrameworkConfig, default_config_yaml, load_config


def test_defaults_when_no_file(workspace):
    loaded = load_config()
    assert loaded.source is None
    assert loaded.config == FrameworkConfig()
    assert loaded.config.lab.authorized is False  # safe by default


def test_generated_yaml_round_trips(workspace):
    p = workspace / "configs" / "framework.yaml"
    p.parent.mkdir()
    p.write_text(default_config_yaml())
    loaded = load_config()
    assert loaded.source == p.resolve()
    assert loaded.root == workspace.resolve()
    assert loaded.config == FrameworkConfig()


def test_env_var_selects_file(workspace, monkeypatch):
    p = workspace / "custom.yaml"
    p.write_text("seed: 7\n")
    monkeypatch.setenv("FRAMEWORK_CONFIG", str(p))
    assert load_config().config.seed == 7


@pytest.mark.parametrize(
    "text",
    [
        "seed: [1, 2\n",                 # broken YAML
        "- just\n- a list\n",            # wrong root type
        "seeed: 1\n",                    # unknown key (typo)
        "logging: {level: LOUD}\n",      # invalid enum
    ],
)
def test_invalid_config_rejected(workspace, text):
    p = workspace / "bad.yaml"
    p.write_text(text)
    with pytest.raises(ConfigError):
        load_config(p)


def test_missing_explicit_file(workspace):
    with pytest.raises(ConfigError, match="not found"):
        load_config(workspace / "nope.yaml")
