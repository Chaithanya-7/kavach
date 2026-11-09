"""Framework configuration: YAML file validated by Pydantic.

Resolution order for the config file:
  1. explicit path (``--config``)
  2. ``FRAMEWORK_CONFIG`` environment variable
  3. ``./configs/framework.yaml``
  4. built-in defaults (no file)

All relative paths inside the config are resolved against the workspace root,
which is the directory that contains ``configs/`` (or the CWD when no file is used).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

DEFAULT_CONFIG_RELPATH = Path("configs") / "framework.yaml"
ENV_VAR = "FRAMEWORK_CONFIG"


class ConfigError(Exception):
    """Raised when the configuration file is missing, unreadable or invalid."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # typos in YAML keys must fail loudly


class PathsConfig(_Strict):
    experiments_dir: Path = Path("experiments")
    outputs_dir: Path = Path("outputs")
    database: Path = Path("experiments") / "framework.db"


class LoggingConfig(_Strict):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file: Path = Path("outputs") / "logs" / "framework.jsonl"


class LabConfig(_Strict):
    """Safety gate: scenarios will refuse to execute until the researcher confirms an isolated lab."""

    authorized: bool = False
    name: str = "unnamed-lab"
    allowed_hostnames: list[str] = Field(default_factory=list)


class FrameworkConfig(_Strict):
    seed: int = 42
    paths: PathsConfig = Field(default_factory=PathsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    lab: LabConfig = Field(default_factory=LabConfig)


class LoadedConfig(BaseModel):
    """A validated config plus where it came from."""

    config: FrameworkConfig
    source: Path | None  # None => built-in defaults
    root: Path

    def resolve(self, p: Path) -> Path:
        return p if p.is_absolute() else (self.root / p)

    @property
    def output_dirs(self) -> list[Path]:
        out = self.resolve(self.config.paths.outputs_dir)
        return [
            self.resolve(self.config.paths.experiments_dir),
            out / "logs",
            out / "models",
            out / "graphs",
            out / "reports",
        ]


def find_config(explicit: Path | None = None) -> Path | None:
    if explicit is not None:
        return explicit
    env = os.environ.get(ENV_VAR)
    if env:
        return Path(env)
    candidate = Path.cwd() / DEFAULT_CONFIG_RELPATH
    return candidate if candidate.is_file() else None


def load_config(explicit: Path | None = None) -> LoadedConfig:
    path = find_config(explicit)
    if path is None:
        return LoadedConfig(config=FrameworkConfig(), source=None, root=Path.cwd())
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a mapping in {path}")
    try:
        cfg = FrameworkConfig.model_validate(data)
    except ValidationError as e:
        raise ConfigError(f"Invalid configuration in {path}:\n{e}") from e
    path = path.resolve()
    # configs/framework.yaml -> workspace root is the parent of configs/
    root = path.parent.parent if path.parent.name == "configs" else path.parent
    return LoadedConfig(config=cfg, source=path, root=root)


def default_config_yaml() -> str:
    """YAML text for ``framework init``, generated from the model so it never drifts."""
    data = FrameworkConfig().model_dump(mode="json")
    header = (
        "# Adaptive Endpoint Framework configuration.\n"
        "# Relative paths resolve against the workspace root (parent of configs/).\n"
        "# Set lab.authorized: true ONLY inside an isolated, authorized Windows test VM.\n"
    )
    return header + yaml.safe_dump(data, sort_keys=False)
