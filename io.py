from pathlib import Path

import yaml

from llminator.config.models import SuiteConfig, TargetsConfig


def _read_yaml(path: Path) -> object:
    if not path.exists():
        raise FileNotFoundError(f"configuration file not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_targets(path: Path) -> TargetsConfig:
    return TargetsConfig.model_validate(_read_yaml(path))


def save_targets(path: Path, config: TargetsConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )


def load_suite(path: Path) -> SuiteConfig:
    return SuiteConfig.model_validate(_read_yaml(path))

