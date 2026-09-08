from llminator.config.models import MLTargetConfig


def test_onnx_is_black_box() -> None:
    target = MLTargetConfig(
        name="fixture",
        format="onnx",
        path="fixture.onnx",
        input_shape=[1, 2],
    )
    assert target.access_mode == "black_box"


def test_pytorch_is_white_box() -> None:
    target = MLTargetConfig(
        name="fixture",
        format="pytorch",
        path="fixture.pt",
        input_shape=[1, 2],
    )
    assert target.access_mode == "white_box"

