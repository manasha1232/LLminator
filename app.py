from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from llminator import __version__
from llminator.config.io import load_suite, load_targets, save_targets
from llminator.config.models import (
    DatasetConfig,
    LLMTargetConfig,
    MLTargetConfig,
    TargetsConfig,
)
from llminator.engines.art_engine import run_art_check
from llminator.engines.internal_checks import run_internal_llm_check
from llminator.engines.garak_engine import run_garak_check
from llminator.engines.onnx_engine import run_onnx_audit
from llminator.reporting.schema import ScanReport, build_report
from llminator.reporting.terminal_report import render_report
from llminator.targets.factory import create_target

app = typer.Typer(
    help="Audit ML and LLM systems from the command line.",
    invoke_without_command=True,
    no_args_is_help=False,
)
target_app = typer.Typer(help="Manage configured scan targets.")
app.add_typer(target_app, name="target")
console = Console()

_ASCII_LOGO = (
    "██╗     ██╗     ███╗   ███╗██╗███╗   ██╗ █████╗ ████████╗ ██████╗ ██████╗ ",
    "██║     ██║     ████╗ ████║██║████╗  ██║██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗",
    "██║     ██║     ██╔████╔██║██║██╔██╗ ██║███████║   ██║   ██║   ██║██████╔╝",
    "██║     ██║     ██║╚██╔╝██║██║██║╚██╗██║██╔══██║   ██║   ██║   ██║██╔══██╗",
    "███████╗███████╗██║ ╚═╝ ██║██║██║ ╚████║██║  ██║   ██║   ╚██████╔╝██║  ██║",
    "╚══════╝╚══════╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝",
)


def _logo() -> Text:
    """Return a terminal-width-aware LLMinator wordmark."""
    if console.width < 96:
        return Text.assemble(
            ("LLM", "bold cyan"),
            ("INATOR", "bold bright_magenta"),
            ("\nAI SECURITY CLI", "dim"),
        )
    logo = Text()
    for index, line in enumerate(_ASCII_LOGO):
        style = "bold cyan" if index < 3 else "bold bright_magenta"
        logo.append(line, style=style)
        if index < len(_ASCII_LOGO) - 1:
            logo.append("\n")
    return logo


def _banner() -> None:
    console.print(
        Panel(
            Text.assemble(
                _logo(),
                "\n",
                ("AI security testing from your terminal", "dim"),
            ),
            title="[bold white]◈ ADVERSARIAL TESTING CONSOLE ◈[/bold white]",
            subtitle=f"[dim]v{__version__}[/dim]",
            border_style="bright_magenta",
            padding=(1, 2),
        )
    )


def _choose(label: str, choices: list[str]) -> str:
    if not choices:
        raise typer.BadParameter(f"no {label.lower()} options are available")
    console.print(f"\n[bold]{label}[/bold]")
    for index, choice in enumerate(choices, 1):
        console.print(f"  [cyan]{index}[/cyan]  {choice}")
    selected = IntPrompt.ask("Select", choices=[str(i) for i in range(1, len(choices) + 1)])
    return choices[selected - 1]


def _config_dir(value: Path) -> Path:
    return value.expanduser().resolve()


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-") or "target"


def _garak_check():
    from llminator.config.models import SuiteCheck

    return SuiteCheck(
        engine="garak",
        check="bounded_redteam",
        parameters={
            "probes": [
                "promptinject.HijackHateHumans",
                "encoding.InjectBase64",
                "dan.DanInTheWild",
            ],
            "prompt_cap": 1,
            "generations": 1,
            "timeout_seconds": 600,
        },
    )


def _direct_suite(
    target_type: str,
    model_format: str | None = None,
    deep: bool = False,
):
    from llminator.config.models import SuiteConfig, SuiteCheck

    if target_type == "llm":
        checks = [
            SuiteCheck(
                engine="internal",
                check="availability_latency",
                parameters={"repetitions": 2, "warning_threshold_ms": 30000},
            ),
            SuiteCheck(
                engine="internal",
                check="deterministic_consistency",
                parameters={"repetitions": 3},
            ),
            SuiteCheck(engine="internal", check="error_handling"),
        ]
        if deep:
            checks.append(_garak_check())
        return SuiteConfig(
            name="llm-baseline",
            target_type="llm",
            checks=checks,
        )
    if model_format == "onnx":
        return SuiteConfig(
            name="onnx-baseline",
            target_type="ml",
            checks=[SuiteCheck(engine="onnx", check="model_audit")],
        )
    raise typer.BadParameter("no built-in suite exists for this direct target")


@app.callback()
def main_callback(ctx: typer.Context) -> None:
    """LLMinator command-line entry point."""
    if ctx.invoked_subcommand is not None:
        return
    if console.is_terminal:
        menu_command()
    else:
        console.print(ctx.get_help())


@app.command("init")
def init_command(
    config_dir: Annotated[Path, typer.Option("--config-dir")] = Path(".llminator"),
    force: Annotated[bool, typer.Option(help="Replace scaffold files.")] = False,
) -> None:
    """Create a target registry and baseline suites."""
    root = _config_dir(config_dir)
    suites = root / "suites"
    root.mkdir(parents=True, exist_ok=True)
    suites.mkdir(parents=True, exist_ok=True)
    files = {
        root / "targets.yaml": {"targets": []},
        suites / "ml-baseline.yaml": {
            "name": "ml-baseline",
            "target_type": "ml",
            "checks": [{"engine": "art", "attack": "fgsm", "epsilon": 0.03}],
        },
        suites / "llm-baseline.yaml": {
            "name": "llm-baseline",
            "target_type": "llm",
            "checks": [
                {
                    "engine": "internal",
                    "check": "availability_latency",
                    "parameters": {"repetitions": 2, "warning_threshold_ms": 30000},
                },
                {
                    "engine": "internal",
                    "check": "deterministic_consistency",
                    "parameters": {"repetitions": 3},
                },
                {"engine": "internal", "check": "error_handling"},
            ],
        },
    }
    for path, content in files.items():
        if path.exists() and not force:
            continue
        path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")
    console.print(f"[green]Initialized[/green] {root}")


@target_app.command("add")
def target_add(
    name: Annotated[str, typer.Option("--name")],
    target_type: Annotated[str, typer.Option("--type")],
    config_dir: Annotated[Path, typer.Option("--config-dir")] = Path(".llminator"),
    model_format: Annotated[Optional[str], typer.Option("--format")] = None,
    path: Annotated[Optional[Path], typer.Option("--path")] = None,
    task: Annotated[str, typer.Option("--task")] = "classification",
    input_shape: Annotated[Optional[str], typer.Option("--input-shape")] = None,
    dataset_path: Annotated[Optional[Path], typer.Option("--dataset-path")] = None,
    provider: Annotated[Optional[str], typer.Option("--provider")] = None,
    model: Annotated[Optional[str], typer.Option("--model")] = None,
    endpoint: Annotated[Optional[str], typer.Option("--endpoint")] = None,
    api_key_env: Annotated[Optional[str], typer.Option("--api-key-env")] = None,
) -> None:
    """Register an ML or LLM target."""
    registry_path = _config_dir(config_dir) / "targets.yaml"
    registry = load_targets(registry_path) if registry_path.exists() else TargetsConfig()
    if any(item.name == name for item in registry.targets):
        raise typer.BadParameter(f"target {name!r} already exists")

    if target_type == "ml":
        if not model_format or not path or not input_shape:
            raise typer.BadParameter("ML targets require --format, --path, and --input-shape")
        shape = [int(part.strip()) for part in input_shape.split(",")]
        dataset = DatasetConfig(path=str(dataset_path)) if dataset_path else None
        item = MLTargetConfig(
            name=name,
            format=model_format,
            path=str(path),
            task=task,
            input_shape=shape,
            dataset=dataset,
        )
    elif target_type == "llm":
        if not provider or not endpoint:
            raise typer.BadParameter("LLM targets require --provider and --endpoint")
        item = LLMTargetConfig(
            name=name,
            provider=provider,
            model=model,
            endpoint=endpoint,
            api_key_env=api_key_env,
        )
    else:
        raise typer.BadParameter("--type must be ml or llm")

    registry.targets.append(item)
    save_targets(registry_path, registry)
    console.print(f"[green]Added[/green] {name}")


@target_app.command("list")
def target_list(
    config_dir: Annotated[Path, typer.Option("--config-dir")] = Path(".llminator"),
) -> None:
    """List registered targets."""
    registry = load_targets(_config_dir(config_dir) / "targets.yaml")
    if not registry.targets:
        console.print("No targets configured.")
        return
    table = Table(title="Configured targets", border_style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Adapter")
    table.add_column("Target")
    table.add_column("Access")
    for target in registry.targets:
        detail = target.format if target.type == "ml" else target.provider
        destination = target.path if target.type == "ml" else (target.model or str(target.endpoint))
        access = target.access_mode if target.type == "ml" else "black_box"
        table.add_row(target.name, target.type.upper(), detail, destination, access)
    console.print(table)


@app.command("scan")
def scan_command(
    target_name: Annotated[
        Optional[str], typer.Argument(help="Configured target name.")
    ] = None,
    target_option: Annotated[
        Optional[str],
        typer.Option("--target", help="Configured target name (legacy flag)."),
    ] = None,
    llm: Annotated[
        Optional[str],
        typer.Option(
            "--llm",
            help="Ollama model name, e.g. qwen3.5:9b.",
        ),
    ] = None,
    onnx_path: Annotated[
        Optional[Path],
        typer.Option(
            "--onnx",
            help="Path to a local ONNX model.",
        ),
    ] = None,
    endpoint: Annotated[
        str,
        typer.Option(
            "--endpoint",
            help="LLM API endpoint.",
        ),
    ] = "http://127.0.0.1:11434/api/chat",
    deep: Annotated[
        bool,
        typer.Option(
            "--deep",
            help="Add bounded garak prompt-injection, encoding, and jailbreak probes.",
        ),
    ] = False,
    suite_name: Annotated[
        Optional[str],
        typer.Option("--suite", help="Suite name; inferred when omitted."),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option("--output", help="JSON path; generated when omitted."),
    ] = None,
    config_dir: Annotated[Path, typer.Option("--config-dir")] = Path(".llminator"),
) -> None:
    """Run a configured suite and write the canonical JSON report."""
    root = _config_dir(config_dir)
    selectors = sum(bool(value) for value in (target_name, target_option, llm, onnx_path))
    if selectors != 1:
        raise typer.BadParameter(
            "choose exactly one target: TARGET_NAME, --llm MODEL, or --onnx PATH"
        )

    direct = llm is not None or onnx_path is not None
    if llm is not None:
        target_name = _safe_name(llm)
        config = LLMTargetConfig(
            name=target_name,
            provider="ollama",
            model=llm,
            endpoint=endpoint,
        )
        suite = _direct_suite("llm", deep=deep)
    elif onnx_path is not None:
        resolved_onnx = onnx_path.expanduser().resolve()
        if not resolved_onnx.is_file():
            raise typer.BadParameter(f"ONNX file not found: {resolved_onnx}")
        target_name = _safe_name(resolved_onnx.stem)
        config = MLTargetConfig(
            name=target_name,
            format="onnx",
            path=str(resolved_onnx),
        )
        suite = _direct_suite("ml", "onnx")
    else:
        target_name = target_name or target_option
        registry = load_targets(root / "targets.yaml")
        config = next((item for item in registry.targets if item.name == target_name), None)
        if config is None:
            raise typer.BadParameter(f"unknown target {target_name!r}")

    if not direct and suite_name is None:
        compatible = [
            load_suite(path)
            for path in sorted((root / "suites").glob("*.yaml"))
            if load_suite(path).target_type == config.type
        ]
        if len(compatible) != 1:
            names = ", ".join(suite.name for suite in compatible) or "none"
            raise typer.BadParameter(
                f"could not infer one suite for {config.type}; compatible suites: {names}"
            )
        suite_name = compatible[0].name
    if not direct:
        suite = load_suite(root / "suites" / f"{suite_name}.yaml")
        if (
            deep
            and config.type == "llm"
            and not any(check.engine == "garak" for check in suite.checks)
        ):
            suite.checks.append(_garak_check())
    if suite.target_type != config.type:
        raise typer.BadParameter("suite target_type does not match the target")

    started_at = datetime.now(timezone.utc)
    target = None
    if not (config.type == "ml" and config.format == "onnx"):
        target = create_target(config, base_dir=root)
    results = []
    scan_heading = Text.assemble(
        ("◆ LLM", "bold cyan"),
        ("INATOR", "bold bright_magenta"),
        (" / SCAN\n", "bold white"),
        (config.name, "bold"),
        (
            f"\n{config.type.upper()}  •  {suite.name}  •  JSON-FIRST REPORT",
            "dim",
        ),
    )
    console.print(
        Panel.fit(
            scan_heading,
            border_style="bright_magenta",
            padding=(0, 2),
        )
    )
    with console.status(
        f"[cyan]Scanning {config.name} with {suite.name}…[/cyan]",
        spinner="dots12",
    ):
        for check in suite.checks:
            if config.type == "ml" and check.engine == "art":
                results.append(run_art_check(target, config, check, base_dir=root))
            elif config.type == "ml" and check.engine == "onnx":
                results.append(run_onnx_audit(config, check, base_dir=root))
            elif config.type == "llm" and check.engine == "internal":
                results.append(run_internal_llm_check(target, config, check))
            elif config.type == "llm" and check.engine == "garak":
                results.extend(run_garak_check(config, check, base_dir=root))
            else:
                results.append(check.unsupported_result())
    report = build_report(config, suite, results, started_at=started_at)
    if output is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = Path("reports") / f"{target_name}-{stamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    render_report(report, console)
    console.print(f"\nJSON report: [cyan]{output.resolve()}[/cyan]")


def _interactive_add(root: Path) -> None:
    console.print("\n[bold cyan]Register a target[/bold cyan]")
    target_type = _choose("Target type", ["LLM API / Ollama", "ML model"])
    name = Prompt.ask("Target name")
    if target_type.startswith("LLM"):
        provider = _choose("Provider", ["ollama", "custom-http", "openai", "anthropic"])
        model = Prompt.ask("Model name", default="qwen3.5:9b" if provider == "ollama" else "")
        default_endpoint = (
            "http://127.0.0.1:11434/api/chat" if provider == "ollama" else ""
        )
        endpoint = Prompt.ask("Endpoint URL", default=default_endpoint)
        api_key_env = None
        if provider not in {"ollama", "custom-http"}:
            api_key_env = Prompt.ask("API-key environment variable")
        target_add(
            name=name,
            target_type="llm",
            config_dir=root,
            provider=provider,
            model=model or None,
            endpoint=endpoint,
            api_key_env=api_key_env,
        )
        return

    model_format = _choose("Model format", ["pytorch", "onnx"])
    model_path = Path(Prompt.ask("Local model path"))
    input_shape = Prompt.ask("Input shape", default="1,2")
    dataset_text = Prompt.ask("Labelled dataset (.npz), optional", default="")
    target_add(
        name=name,
        target_type="ml",
        config_dir=root,
        model_format=model_format,
        path=model_path,
        input_shape=input_shape,
        dataset_path=Path(dataset_text) if dataset_text else None,
    )


def _interactive_scan(root: Path) -> None:
    registry_path = root / "targets.yaml"
    if not registry_path.exists():
        console.print("[yellow]No configuration found. Initializing it now.[/yellow]")
        init_command(config_dir=root)
    registry = load_targets(registry_path)
    if not registry.targets:
        console.print("[yellow]Register a target before running a scan.[/yellow]")
        _interactive_add(root)
        registry = load_targets(registry_path)

    names = [item.name for item in registry.targets]
    target_name = _choose("Scan target", names)
    selected = next(item for item in registry.targets if item.name == target_name)
    suite_paths = sorted((root / "suites").glob("*.yaml"))
    compatible = [
        load_suite(path).name
        for path in suite_paths
        if load_suite(path).target_type == selected.type
    ]
    suite_name = _choose("Test suite", compatible)
    deep = False
    if selected.type == "llm":
        scan_depth = _choose(
            "Scan depth",
            [
                "Baseline — fast structural checks",
                "Deep — baseline + bounded garak red-team",
            ],
        )
        deep = scan_depth.startswith("Deep")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = Path("reports") / f"{target_name}-{stamp}.json"
    output_text = Prompt.ask("Report path", default=str(output))
    console.print(
        Panel(
            f"Target: [bold]{target_name}[/bold]\n"
            f"Suite:  [bold]{suite_name}[/bold]\n"
            f"Depth:  [bold]{'deep red-team' if deep else 'baseline'}[/bold]\n"
            f"Output: {output_text}",
            title="Scan plan",
            border_style="bright_magenta",
        )
    )
    if Confirm.ask("Start scan?", default=True):
        scan_command(
            target_name=target_name,
            target_option=None,
            suite_name=suite_name,
            output=Path(output_text),
            config_dir=root,
            deep=deep,
        )


@app.command("targets")
def targets_shortcut() -> None:
    """Show configured targets."""
    target_list(config_dir=Path(".llminator"))


@app.command("add")
def add_shortcut() -> None:
    """Interactively register an ML model or LLM."""
    root = _config_dir(Path(".llminator"))
    if not (root / "targets.yaml").exists():
        init_command(config_dir=root)
    _banner()
    _interactive_add(root)


@app.command("menu")
def menu_command(
    config_dir: Annotated[Path, typer.Option("--config-dir")] = Path(".llminator"),
) -> None:
    """Open the guided interactive interface."""
    root = _config_dir(config_dir)
    _banner()
    while True:
        action = _choose(
            "What would you like to do?",
            ["Run a scan", "List targets", "Add a target", "Initialize config", "Exit"],
        )
        try:
            if action == "Run a scan":
                _interactive_scan(root)
            elif action == "List targets":
                target_list(config_dir=root)
            elif action == "Add a target":
                _interactive_add(root)
            elif action == "Initialize config":
                init_command(config_dir=root)
            else:
                console.print("\n[dim]Threats terminated. Stay sharp.[/dim]")
                return
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Could not complete action:[/red] {exc}")
        console.print()


@app.command("version")
def version_command() -> None:
    console.print(__version__)
