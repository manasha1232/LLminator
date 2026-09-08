from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from llminator.reporting.schema import CheckResult


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetConfig(StrictModel):
    path: str
    inputs_key: str = "x"
    labels_key: str = "y"
    sample_limit: int | None = Field(default=None, gt=0)


class MLTargetConfig(StrictModel):
    name: str
    type: Literal["ml"] = "ml"
    format: Literal["pytorch", "onnx"]
    path: str
    task: Literal["classification"] = "classification"
    input_shape: list[int] = Field(default_factory=lambda: [1])
    clip_values: tuple[float, float] = (0.0, 1.0)
    dataset: DatasetConfig | None = None
    access_mode: Literal["white_box", "black_box"] | None = None

    @model_validator(mode="after")
    def infer_access_mode(self) -> "MLTargetConfig":
        expected = "white_box" if self.format == "pytorch" else "black_box"
        if self.access_mode is None:
            self.access_mode = expected
        if self.format == "onnx" and self.access_mode == "white_box":
            raise ValueError("generic ONNX targets cannot declare white_box access")
        return self


class LLMTargetConfig(StrictModel):
    name: str
    type: Literal["llm"] = "llm"
    provider: str
    model: str | None = None
    endpoint: HttpUrl
    api_key_env: str | None = None
    rate_limit_rps: float | None = Field(default=None, gt=0)


TargetConfig = MLTargetConfig | LLMTargetConfig


class TargetsConfig(StrictModel):
    targets: list[TargetConfig] = Field(default_factory=list)


class SuiteCheck(StrictModel):
    engine: str
    check: str | None = None
    attack: str | None = None
    epsilon: float | None = Field(default=None, gt=0)
    steps: int | None = Field(default=None, gt=0)
    parameters: dict[str, Any] = Field(default_factory=dict)

    def unsupported_result(self) -> CheckResult:
        return CheckResult(
            engine=self.engine,
            check=self.check or self.attack or "unknown",
            status="skipped",
            severity="info",
            details=f"Engine {self.engine!r} is not implemented in this release.",
        )


class SuiteConfig(StrictModel):
    name: str
    target_type: Literal["ml", "llm"]
    checks: list[SuiteCheck]
