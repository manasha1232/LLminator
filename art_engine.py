from __future__ import annotations

from pathlib import Path
from time import perf_counter

import numpy as np

from llminator.config.models import MLTargetConfig, SuiteCheck
from llminator.reporting.schema import CheckResult
from llminator.targets.base import MLTarget
from llminator.targets.ml_target import PyTorchTarget


def _resolve(path: str, base_dir: Path) -> Path:
    candidate = Path(path).expanduser()
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def run_art_check(
    target: MLTarget,
    config: MLTargetConfig,
    check: SuiteCheck,
    base_dir: Path,
) -> CheckResult:
    started = perf_counter()
    if check.attack != "fgsm":
        return CheckResult(
            engine="art",
            check=check.attack or "unknown",
            status="skipped",
            severity="info",
            details="Only FGSM is implemented in v0.1.",
        )
    if not isinstance(target, PyTorchTarget):
        return CheckResult(
            engine="art",
            check="fgsm",
            status="skipped",
            severity="info",
            details="FGSM requires a differentiable white-box target; generic ONNX is black-box.",
        )
    if config.dataset is None:
        return CheckResult(
            engine="art",
            check="fgsm",
            status="error",
            severity="info",
            details="FGSM requires a configured labelled dataset.",
        )
    try:
        import torch
        from art.attacks.evasion import FastGradientMethod
        from art.estimators.classification import PyTorchClassifier

        dataset_path = _resolve(config.dataset.path, base_dir)
        with np.load(dataset_path) as data:
            x = data[config.dataset.inputs_key].astype(np.float32)
            y = data[config.dataset.labels_key].astype(np.int64)
        if config.dataset.sample_limit:
            x, y = x[: config.dataset.sample_limit], y[: config.dataset.sample_limit]

        clean_logits = target.predict(x)
        class_count = int(clean_logits.shape[1])
        classifier = PyTorchClassifier(
            model=target.model,
            loss=torch.nn.CrossEntropyLoss(),
            input_shape=tuple(config.input_shape[1:]),
            nb_classes=class_count,
            clip_values=config.clip_values,
        )
        epsilon = check.epsilon or 0.03
        adversarial = FastGradientMethod(estimator=classifier, eps=epsilon).generate(x=x, y=y)
        adversarial_logits = target.predict(adversarial)
        clean_accuracy = float(np.mean(np.argmax(clean_logits, axis=1) == y))
        robust_accuracy = float(np.mean(np.argmax(adversarial_logits, axis=1) == y))
        attack_success_rate = float(
            np.mean(
                (np.argmax(clean_logits, axis=1) == y)
                & (np.argmax(adversarial_logits, axis=1) != y)
            )
        )
        failed = robust_accuracy < clean_accuracy
        return CheckResult(
            engine="art",
            check="fgsm",
            status="fail" if failed else "pass",
            severity="high" if attack_success_rate >= 0.25 else ("medium" if failed else "info"),
            details=(
                f"Clean accuracy {clean_accuracy:.1%}; adversarial accuracy "
                f"{robust_accuracy:.1%} at epsilon={epsilon}."
            ),
            duration_ms=round((perf_counter() - started) * 1000, 2),
            evidence={
                "samples": len(x),
                "epsilon": epsilon,
                "clean_accuracy": clean_accuracy,
                "adversarial_accuracy": robust_accuracy,
                "attack_success_rate": attack_success_rate,
            },
            remediation=[
                "Evaluate bounded adversarial training and measure the clean/robust accuracy trade-off.",
                "Verify preprocessing, feature ranges, and epsilon against the production threat model.",
                "Add this dataset and threshold as a repeatable robustness regression test.",
            ],
        )
    except Exception as exc:
        return CheckResult(
            engine="art",
            check="fgsm",
            status="error",
            severity="info",
            details=f"{type(exc).__name__}: {exc}",
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )

