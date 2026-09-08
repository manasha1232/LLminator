"""Create a tiny deterministic ONNX classifier for CLI smoke tests."""

from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper


def main() -> None:
    weights = numpy_helper.from_array(
        np.array([[2.0, -2.0], [-1.5, 1.5]], dtype=np.float32),
        name="weights",
    )
    bias = numpy_helper.from_array(
        np.array([0.1, -0.1], dtype=np.float32),
        name="bias",
    )
    graph = helper.make_graph(
        [
            helper.make_node("MatMul", ["features", "weights"], ["linear"]),
            helper.make_node("Add", ["linear", "bias"], ["logits"]),
        ],
        "tiny_classifier",
        [helper.make_tensor_value_info("features", TensorProto.FLOAT, ["batch", 2])],
        [helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["batch", 2])],
        [weights, bias],
    )
    model = helper.make_model(
        graph,
        producer_name="llminator-fixture",
        opset_imports=[helper.make_opsetid("", 13)],
    )
    onnx.checker.check_model(model)
    destination = Path("examples/models/tiny_classifier.onnx")
    destination.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, destination)
    print(destination)


if __name__ == "__main__":
    main()
