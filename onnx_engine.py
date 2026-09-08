from __future__ import annotations

import hashlib
from pathlib import Path
from time import perf_counter

from llminator.config.models import MLTargetConfig, SuiteCheck
from llminator.reporting.schema import CheckResult


def _resolve(path: str, base_dir: Path) -> Path:
    candidate = Path(path).expanduser()
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def _dimensions(value_info: object) -> list[int | str]:
    dimensions: list[int | str] = []
    tensor_type = value_info.type.tensor_type
    for dimension in tensor_type.shape.dim:
        if dimension.dim_value:
            dimensions.append(dimension.dim_value)
        elif dimension.dim_param:
            dimensions.append(dimension.dim_param)
        else:
            dimensions.append("?")
    return dimensions


def run_onnx_audit(
    config: MLTargetConfig,
    check: SuiteCheck,
    base_dir: Path,
) -> CheckResult:
    started = perf_counter()
    path = _resolve(config.path, base_dir)
    try:
        import onnx

        model = onnx.load(path, load_external_data=False)
        onnx.checker.check_model(model)
        graph = model.graph
        initializer_names = {item.name for item in graph.initializer}
        inputs = [
            {
                "name": item.name,
                "shape": _dimensions(item),
                "element_type": item.type.tensor_type.elem_type,
            }
            for item in graph.input
            if item.name not in initializer_names
        ]
        outputs = [
            {
                "name": item.name,
                "shape": _dimensions(item),
                "element_type": item.type.tensor_type.elem_type,
            }
            for item in graph.output
        ]
        opsets = [
            {"domain": item.domain or "ai.onnx", "version": item.version}
            for item in model.opset_import
        ]
        dynamic = any(
            not isinstance(value, int)
            for item in inputs
            for value in item["shape"]
        )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        recommendations = [
            "Validate all runtime inputs against the reported dtype, rank, and allowed dimensions.",
            "Benchmark clean accuracy on a labelled representative dataset before adversarial testing.",
            "Run the model with a restricted service account and enforce request size and timeout limits.",
        ]
        if dynamic:
            recommendations.insert(
                0,
                "Bound dynamic input dimensions at the serving layer to prevent memory exhaustion.",
            )
        return CheckResult(
            engine="onnx",
            check=check.check or "model_audit",
            status="pass",
            severity="info",
            details=(
                f"Valid ONNX graph with {len(graph.node)} nodes, "
                f"{len(inputs)} runtime input(s), and {len(outputs)} output(s)."
            ),
            duration_ms=round((perf_counter() - started) * 1000, 2),
            evidence={
                "path": str(path),
                "sha256": digest,
                "size_bytes": path.stat().st_size,
                "ir_version": model.ir_version,
                "producer": model.producer_name or None,
                "opsets": opsets,
                "node_count": len(graph.node),
                "inputs": inputs,
                "outputs": outputs,
                "dynamic_input_dimensions": dynamic,
            },
            remediation=recommendations,
        )
    except ImportError:
        return CheckResult(
            engine="onnx",
            check=check.check or "model_audit",
            status="error",
            severity="info",
            details="ONNX support is not installed; run: uv pip install 'llminator[ml]'",
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
    except Exception as exc:
        return CheckResult(
            engine="onnx",
            check=check.check or "model_audit",
            status="fail",
            severity="high",
            details=f"ONNX validation failed: {type(exc).__name__}: {exc}",
            duration_ms=round((perf_counter() - started) * 1000, 2),
            remediation=[
                "Reject the model artifact until it passes ONNX structural validation.",
                "Re-export it using a supported opset and verify its SHA-256 provenance.",
            ],
        )
