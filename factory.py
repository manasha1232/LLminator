from pathlib import Path

from llminator.config.models import LLMTargetConfig, MLTargetConfig, TargetConfig
from llminator.targets.base import Target
from llminator.targets.llm_target import HTTPLLMTarget
from llminator.targets.ml_target import ONNXTarget, PyTorchTarget


def _resolve(path: str, base_dir: Path) -> Path:
    candidate = Path(path).expanduser()
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def create_target(config: TargetConfig, base_dir: Path) -> Target:
    if isinstance(config, LLMTargetConfig):
        return HTTPLLMTarget(config)
    path = _resolve(config.path, base_dir)
    shape = tuple(config.input_shape)
    if config.format == "pytorch":
        return PyTorchTarget(config.name, path, shape)
    if config.format == "onnx":
        return ONNXTarget(config.name, path, shape)
    raise ValueError(f"unsupported target format: {config.format}")

