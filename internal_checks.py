from __future__ import annotations

import json
import statistics
import urllib.error
import urllib.request
from time import perf_counter

from llminator.config.models import LLMTargetConfig, SuiteCheck
from llminator.reporting.schema import CheckResult
from llminator.targets.base import LLMTarget


_BENIGN_PROMPT = (
    "Reply with exactly one short sentence explaining why software tests are useful."
)


def _generate(target: LLMTarget) -> tuple[str, float]:
    started = perf_counter()
    response = target.generate(
        _BENIGN_PROMPT,
        temperature=0,
        max_tokens=96,
        timeout=180,
    )
    return response, (perf_counter() - started) * 1000


def _availability_latency(
    target: LLMTarget, check: SuiteCheck
) -> CheckResult:
    started = perf_counter()
    repetitions = int(check.parameters.get("repetitions", 2))
    warning_threshold = float(check.parameters.get("warning_threshold_ms", 30000))
    try:
        samples = [_generate(target) for _ in range(repetitions)]
        latencies = [sample[1] for sample in samples]
        empty = sum(not sample[0].strip() for sample in samples)
        median = statistics.median(latencies)
        failed = empty > 0
        slow = median > warning_threshold
        return CheckResult(
            engine="internal",
            check="availability_latency",
            status="fail" if failed else "pass",
            severity="medium" if failed else ("low" if slow else "info"),
            details=(
                f"{repetitions - empty}/{repetitions} requests returned content; "
                f"median latency {median:.0f} ms."
            ),
            duration_ms=round((perf_counter() - started) * 1000, 2),
            evidence={
                "requests": repetitions,
                "successful_nonempty_responses": repetitions - empty,
                "latency_ms": [round(value, 2) for value in latencies],
                "median_latency_ms": round(median, 2),
                "warning_threshold_ms": warning_threshold,
            },
            remediation=(
                [
                    "Inspect model loading, token limits, and server logs for empty responses."
                ]
                if failed
                else (
                    [
                        "Warm the model before serving traffic and set explicit request timeouts.",
                        "Measure latency under representative concurrent load.",
                    ]
                    if slow
                    else [
                        "Repeat this check under representative concurrency and enforce request timeouts."
                    ]
                )
            ),
        )
    except Exception as exc:
        return CheckResult(
            engine="internal",
            check="availability_latency",
            status="error",
            severity="info",
            details=f"{type(exc).__name__}: {exc}",
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )


def _deterministic_consistency(
    target: LLMTarget, check: SuiteCheck
) -> CheckResult:
    started = perf_counter()
    repetitions = int(check.parameters.get("repetitions", 3))
    try:
        responses = [_generate(target)[0].strip() for _ in range(repetitions)]
        nonempty = sum(bool(response) for response in responses)
        unique = len(set(responses))
        consistent = unique == 1 and nonempty == repetitions
        return CheckResult(
            engine="internal",
            check="deterministic_consistency",
            status="pass" if consistent else "fail",
            severity="info" if consistent else "low",
            details=(
                f"{unique} unique normalized responses and {nonempty}/{repetitions} "
                "non-empty responses at temperature=0."
            ),
            duration_ms=round((perf_counter() - started) * 1000, 2),
            evidence={
                "requests": repetitions,
                "unique_responses": unique,
                "nonempty_responses": nonempty,
                "response_lengths": [len(value) for value in responses],
                "responses": responses,
            },
            remediation=(
                [
                    "Retain this prompt as a deterministic deployment regression test."
                ]
                if consistent
                else [
                    "Pin model, template, seed, and decoding parameters where reproducibility matters.",
                    "Use semantic comparison for production regression thresholds rather than exact text alone.",
                ]
            ),
        )
    except Exception as exc:
        return CheckResult(
            engine="internal",
            check="deterministic_consistency",
            status="error",
            severity="info",
            details=f"{type(exc).__name__}: {exc}",
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )


def _error_handling(config: LLMTargetConfig) -> CheckResult:
    started = perf_counter()
    request = urllib.request.Request(
        str(config.endpoint),
        data=b'{"model":',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            body = response.read(4096).decode(errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read(4096).decode(errors="replace")
    except Exception as exc:
        return CheckResult(
            engine="internal",
            check="error_handling",
            status="error",
            severity="info",
            details=f"{type(exc).__name__}: {exc}",
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )

    disclosure_terms = ("traceback", "stack trace", "file \"/", "panic:", "goroutine ")
    disclosed = [term for term in disclosure_terms if term in body.lower()]
    safe_status = 400 <= status < 500
    passed = safe_status and not disclosed
    return CheckResult(
        engine="internal",
        check="error_handling",
        status="pass" if passed else "fail",
        severity="info" if passed else "medium",
        details=f"Malformed JSON returned HTTP {status}; stack disclosure markers: {len(disclosed)}.",
        duration_ms=round((perf_counter() - started) * 1000, 2),
        evidence={
            "http_status": status,
            "response_excerpt": body[:500],
            "disclosure_markers": disclosed,
        },
        remediation=(
            [
                "Keep client errors generic and retain detailed diagnostics only in access-controlled server logs."
            ]
            if passed
            else [
                "Return a generic 4xx response for malformed client input.",
                "Keep stack traces and internal paths in server-side logs only.",
            ]
        ),
    )


def run_internal_llm_check(
    target: LLMTarget,
    config: LLMTargetConfig,
    check: SuiteCheck,
) -> CheckResult:
    if check.check == "availability_latency":
        return _availability_latency(target, check)
    if check.check == "deterministic_consistency":
        return _deterministic_consistency(target, check)
    if check.check == "error_handling":
        return _error_handling(config)
    return check.unsupported_result()
