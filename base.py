from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

import numpy as np


class Target(ABC):
    def __init__(self, name: str, target_type: Literal["ml", "llm"]) -> None:
        self.name = name
        self.type = target_type


class MLTarget(Target, ABC):
    def __init__(self, name: str) -> None:
        super().__init__(name, "ml")

    @abstractmethod
    def predict(self, input_batch: np.ndarray) -> np.ndarray: ...

    @property
    @abstractmethod
    def input_shape(self) -> tuple[int, ...]: ...


class LLMTarget(Target, ABC):
    def __init__(self, name: str) -> None:
        super().__init__(name, "llm")

    @abstractmethod
    def generate(self, prompt: str, **kwargs: object) -> str: ...

