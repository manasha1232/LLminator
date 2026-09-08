# Shipping and Installation

## Release contents

The LLMinator release ZIP contains the source package, installer,
documentation, tests, and small generated example models. It deliberately
excludes:

- Virtual environments and dependency caches
- User model weights
- API keys and environment files
- Local target configuration
- Scan reports and raw garak artifacts
- Git metadata

Compiled ML dependencies differ by operating system, CPU architecture, and GPU
runtime. The installer therefore downloads compatible packages on the target
device instead of bundling the developer machine's binaries.

## Requirements

- Linux or macOS
- Bash
- Python 3.11 or 3.12
- Internet access during installation
- `uv` is recommended; standard `venv` and `pip` are supported as a fallback

## Install from the ZIP

```bash
unzip llminator-0.1.0.zip
cd llminator-0.1.0
chmod +x install.sh
./install.sh
```

Installation profiles:

```bash
./install.sh --core    # CLI and LLM baseline
./install.sh --ml      # core + ART/PyTorch/ONNX
./install.sh --garak   # core + isolated garak deep scans
./install.sh --full    # ML + isolated garak
```

Install somewhere else:

```bash
./install.sh --full --prefix /opt/llminator
```

Use a Python interpreter that is not globally available:

```bash
./install.sh --full --python /path/to/python3.11
```

The same value can be provided through `LLMINATOR_PYTHON`.

The default installation locations are:

```text
~/.local/share/llminator/venv
~/.local/share/llminator/garak-venv
~/.local/bin/llminator
```

Ensure `~/.local/bin` is on `PATH`.

## Verify the archive

```bash
sha256sum -c llminator-0.1.0.zip.sha256
```

## First scans

```bash
llminator scan --onnx ./model.onnx
llminator scan --llm qwen3.5:9b
llminator scan --llm qwen3.5:9b --deep
```

Ollama must already be installed and running for local LLM scans. LLMinator
does not distribute Ollama models or automatically download model weights.

## Uninstall

The installer keeps everything under one installation root. Remove it and the
command symlink:

```bash
rm -r ~/.local/share/llminator
rm ~/.local/bin/llminator
```

Review both paths before running removal commands if custom installation
locations were used.
