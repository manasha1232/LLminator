from __future__ import annotations

from pathlib import Path

import numpy as np

from llminator.targets.base import MLTarget


class PyTorchTarget(MLTarget):
    def __init__(self, name: str, path: Path, shape: tuple[int, ...]) -> None:
        super().__init__(name)
        import torch

        self.model = torch.jit.load(str(path), map_location="cpu")
        self.model.eval()
        self._input_shape = shape

    @property
    def input_shape(self) -> tuple[int, ...]:
        return self._input_shape

    def predict(self, input_batch: np.ndarray) -> np.ndarray:
        import torch

        with torch.no_grad():
            output = self.model(torch.as_tensor(input_batch, dtype=torch.float32))
        return output.detach().cpu().numpy()


class ONNXTarget(MLTarget):
    def __init__(self, name: str, path: Path, shape: tuple[int, ...]) -> None:
        super().__init__(name)
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("install LLMinator with the 'ml' extra for ONNX") from exc
        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self._input_shape = shape

    @property
    def input_shape(self) -> tuple[int, ...]:
        return self._input_shape

    def predict(self, input_batch: np.ndarray) -> np.ndarray:
        return self.session.run(None, {self.input_name: input_batch.astype(np.float32)})[0]

