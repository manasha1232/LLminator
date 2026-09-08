# LLMinator CLI Summary

## What LLMinator Does

LLMinator is a CLI-first security and robustness testing tool for machine
learning models and LLM endpoints.

It accepts either:

- A local ONNX model file
- A configured differentiable PyTorch model
- An Ollama model exposed through its local API
- A configured HTTP-based LLM endpoint

Every scan produces a canonical JSON report. The terminal interface reads the
same result objects and presents them as colored tables, summaries, and
recommended next steps.

## Quick Start

Activate the Python environment:

```bash
torch
```

Open the guided interface:

```bash
llminator
```

List configured targets:

```bash
llminator targets
```

Interactively register a target:

```bash
llminator add
```

## Direct Scans

### Scan an Ollama LLM

Ollama must be running:

```bash
ollama serve
```

Run the baseline against an installed Ollama model:

```bash
llminator scan --llm qwen3.5:9b
```

Run a bounded deep scan with maintained garak probes:

```bash
llminator scan --llm qwen3.5:9b --deep
```

The deep scan currently adds one attempt each from maintained prompt-injection,
encoded-instruction, and DAN-style jailbreak probes. It enforces per-request
and overall timeouts. Detector hits must still be reviewed in context because
keyword detectors can match prohibited text quoted inside a refusal.

Specify a different endpoint when necessary:

```bash
llminator scan \
  --llm qwen3.5:9b \
  --endpoint http://127.0.0.1:11434/api/chat
```

`--llm` currently accepts an Ollama model name, not a model-weight upload.
Hosted and custom HTTP targets can instead be registered through
`llminator add` or `llminator target add`.

### Scan an ONNX Model

```bash
llminator scan --onnx ./models/classifier.onnx
```

The direct ONNX baseline performs:

- ONNX graph validation
- SHA-256 artifact fingerprinting
- Model size and producer inspection
- Opset and IR version collection
- Input and output metadata inspection
- Dynamic-input-dimension detection
- Serving and evaluation recommendations

This is a structural audit. It does not measure adversarial accuracy without a
labelled dataset or provide white-box gradients through generic ONNX Runtime.

### Scan a Registered Target

```bash
llminator scan local-qwen
llminator scan sample-classifier
```

LLMinator infers the compatible suite and creates a timestamped report.

Advanced usage remains available:

```bash
llminator scan \
  --target local-qwen \
  --suite llm-baseline \
  --output reports/custom-name.json \
  --config-dir .llminator
```

## Current Scan Checks

### LLM Baseline

The internal LLM baseline currently runs safe structural checks:

1. **Availability and latency**
   - Sends short benign requests.
   - Records individual and median response times.
   - Detects empty responses and request failures.

2. **Deterministic consistency**
   - Repeats the same benign prompt with temperature set to zero.
   - Checks whether responses are non-empty and repeatable.

3. **Error handling**
   - Sends malformed JSON.
   - Checks for an appropriate client-error status.
   - Searches the error response for stack traces, internal paths, panics, and
     similar disclosure markers.

These checks are not a full jailbreak or prompt-injection assessment. Garak and
PyRIT integration is planned for that work so LLMinator does not maintain its
own attack-payload library.

### PyTorch ML Baseline

The current differentiable PyTorch scan uses ART's Fast Gradient Sign Method
(FGSM). It reports:

- Clean accuracy
- Adversarial accuracy
- Attack success rate
- Perturbation epsilon
- Sample count
- Severity and remediation guidance

The target must be a TorchScript classification model with a labelled NumPy
dataset containing:

- `x`: input samples
- `y`: integer class labels

### ONNX Baseline

The ONNX baseline validates and describes the artifact. Generic ONNX inference
is treated as black-box because ONNX Runtime does not universally expose the
loss gradients required by FGSM or PGD.

## Scan and Reporting Pipeline

```text
CLI arguments or YAML configuration
               |
               v
        Pydantic validation
               |
               v
       Target adapter creation
               |
               v
    Engine or internal check execution
               |
               v
       Normalized CheckResult objects
               |
               v
      Canonical versioned JSON report
               |
               +------> Rich terminal presentation
               |
               +------> Future HTML/Markdown reports
```

Reports are saved under `reports/` by default:

```text
reports/<target>-<timestamp>.json
```

Each JSON report includes:

- Schema version and scan UUID
- Target identity and access mode
- Suite name and timestamps
- Pass, fail, error, and skipped counts
- Severity breakdown
- Per-check evidence
- Suggested remediation or hardening steps
- LLMinator version

## Libraries and Toolboxes

### Currently Used

| Library or toolbox | Purpose |
|---|---|
| Python 3.11+ | Runtime and application language |
| Typer | CLI commands, arguments, options, and help output |
| Rich | Branding, panels, tables, prompts, colors, and progress spinners |
| Pydantic | Validation for target, suite, and report schemas |
| PyYAML | Reading and writing target and suite configuration |
| NumPy | Model inputs, datasets, metrics, and numerical operations |
| PyTorch | Differentiable model execution and the sample classifier |
| ART (`adversarial-robustness-toolbox`) | FGSM adversarial attack |
| ONNX | Model parsing, graph checking, and metadata inspection |
| ONNX Runtime | Black-box ONNX inference adapter when installed |
| `urllib` from the Python standard library | HTTP communication with LLM APIs |
| Pytest | Automated tests |

### Planned External Engines

| Engine | Planned purpose |
|---|---|
| Foolbox | Additional ML adversarial and boundary attacks |
| Garak | Maintained LLM vulnerability probes and detectors; bounded deep scan implemented |
| PyRIT | Multi-turn LLM red-team scenarios and scoring |
| Jinja2 | Static HTML report generation |

Garak and PyRIT should supply attack content. LLMinator will focus on target
adapters, orchestration, configuration, normalization, scoring, evidence, and
reporting.

## Project Structure

```text
llminator/
├── cli/                  # Typer commands and interactive terminal interface
├── config/               # Pydantic target and suite models
├── targets/              # PyTorch, ONNX, and HTTP/Ollama adapters
├── engines/              # ART, ONNX, and internal LLM checks
├── reporting/            # Canonical report schema and Rich output
└── main.py               # CLI entry point
```

Example fixtures and generators are under:

```text
examples/
scripts/
```

## Important Limitations

- The present LLM baseline is structural and operational, not a complete
  adversarial red-team suite.
- Direct `--llm` scanning currently assumes an Ollama model.
- Direct ONNX scanning does not determine model accuracy or adversarial
  robustness without representative labelled data.
- FGSM requires differentiable white-box access and cannot be applied
  universally to an arbitrary ONNX artifact.
- Recommendations are reviewable guidance, not automatic fixes.
- Only systems owned by the tester or explicitly authorized for testing should
  be scanned.

## Installing the Release on Another Device

Copy `llminator-0.1.0.zip` and
`llminator-0.1.0.zip.sha256` to the destination, then run:

```bash
sha256sum -c llminator-0.1.0.zip.sha256
unzip llminator-0.1.0.zip
cd llminator-0.1.0
chmod +x install.sh
```

Select the capabilities required on that device:

```bash
./install.sh --core
./install.sh --ml
./install.sh --garak
./install.sh --full
```

Use a specific Python 3.11 or 3.12 interpreter when necessary:

```bash
./install.sh --full --python /path/to/python3.11
```

The default command is installed at:

```text
~/.local/bin/llminator
```

Add that directory to `PATH` if the command is not found:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Verify the installation:

```bash
llminator version
llminator --help
```

See `SHIPPING.md` for the complete packaging and installation guide.
