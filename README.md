# LLMinator

LLMinator is a CLI-first security testing tool for ML and LLM targets. The
current milestone supports a labelled PyTorch classification target and ART's
FGSM attack, producing a canonical JSON report.

## Development quick start

```bash
source /home/b47m4n/torch/bin/activate
uv pip install -e ".[ml,dev]"
python scripts/create_sample_target.py
llminator init
llminator target add --name sample-classifier --type ml --format pytorch \
  --path ../examples/models/tiny_classifier.pt --task classification \
  --input-shape 1,2 --dataset-path ../examples/data/tiny_classifier_test.npz
llminator scan --target sample-classifier --suite ml-baseline --output results.json
```

## Everyday commands

```bash
llminator                 # guided menu
llminator targets         # configured ML and LLM targets
llminator add             # guided target registration
llminator scan TARGET     # infer suite and create a timestamped JSON report
llminator scan --llm qwen3.5:9b
llminator scan --llm qwen3.5:9b --deep
llminator scan --onnx ./model.onnx
```

Explicit `--target`, `--suite`, `--output`, and `--config-dir` flags remain
available for CI and advanced workflows.

## Install on another device

The prepared release consists of:

```text
llminator-0.1.0.zip
llminator-0.1.0.zip.sha256
```

Copy both files to the destination device and verify the archive:

```bash
sha256sum -c llminator-0.1.0.zip.sha256
```

Extract it:

```bash
unzip llminator-0.1.0.zip
cd llminator-0.1.0
chmod +x install.sh
```

Choose an installation profile:

```bash
./install.sh --core    # CLI and LLM baseline
./install.sh --ml      # core + PyTorch, ART, ONNX, and ONNX Runtime
./install.sh --garak   # core + isolated garak deep scanning
./install.sh --full    # ML and garak support
```

Python 3.11 or 3.12 is required. When the interpreter is not globally
available, provide its path:

```bash
./install.sh --full --python /path/to/python3.11
```

Install under a custom directory if necessary:

```bash
./install.sh --full --prefix /opt/llminator
```

The default locations are:

```text
~/.local/share/llminator/venv
~/.local/share/llminator/garak-venv
~/.local/bin/llminator
```

If required, add the command directory to the shell path:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Verify and run:

```bash
llminator version
llminator --help
llminator scan --onnx ./model.onnx
llminator scan --llm qwen3.5:9b
llminator scan --llm qwen3.5:9b --deep
```

Ollama must already be installed and running for local LLM scans:

```bash
ollama serve
```

LLMinator does not package or automatically transfer user model weights,
API keys, scan reports, or local target configuration. Dependencies are
downloaded during installation so the destination receives versions compatible
with its operating system and hardware.

See [SHIPPING.md](SHIPPING.md) for release contents, exclusions, custom
installation, verification, and uninstall information.

Paths in target configuration are resolved relative to the configuration
directory. API keys are referenced by environment-variable name and are never
stored in reports.
