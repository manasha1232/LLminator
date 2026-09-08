from pathlib import Path

from typer.testing import CliRunner

from llminator.cli.app import _direct_suite, _garak_check
from llminator.main import app


runner = CliRunner()


def test_init_and_list_empty_registry(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    initialized = runner.invoke(app, ["init", "--config-dir", str(config_dir)])
    assert initialized.exit_code == 0
    assert (config_dir / "targets.yaml").exists()
    assert (config_dir / "suites" / "ml-baseline.yaml").exists()

    listed = runner.invoke(app, ["target", "list", "--config-dir", str(config_dir)])
    assert listed.exit_code == 0
    assert "No targets configured." in listed.stdout


def test_no_args_prints_help_when_not_interactive() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Audit ML and LLM systems" in result.stdout


def test_menu_can_exit(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["menu", "--config-dir", str(tmp_path / "config")],
        input="5\n",
    )
    assert result.exit_code == 0
    assert "ADVERSARIAL TESTING CONSOLE" in result.stdout
    assert "Threats terminated. Stay sharp." in result.stdout


def test_scan_accepts_short_positional_target(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runner.invoke(app, ["init", "--config-dir", str(config_dir)])
    result = runner.invoke(
        app,
        ["scan", "missing-target", "--config-dir", str(config_dir)],
    )
    assert result.exit_code != 0
    assert "unknown target" in result.output


def test_direct_onnx_requires_existing_file(tmp_path: Path) -> None:
    result = runner.invoke(app, ["scan", "--onnx", str(tmp_path / "missing.onnx")])
    assert result.exit_code != 0
    assert "ONNX file not found" in result.output


def test_direct_selectors_are_mutually_exclusive() -> None:
    result = runner.invoke(
        app,
        ["scan", "registered", "--llm", "qwen3.5:9b"],
    )
    assert result.exit_code != 0
    assert "choose exactly one target" in result.output


def test_deep_llm_suite_adds_bounded_garak_probes() -> None:
    suite = _direct_suite("llm", deep=True)
    garak_check = next(check for check in suite.checks if check.engine == "garak")
    assert garak_check.parameters["prompt_cap"] == 1
    assert garak_check.parameters["generations"] == 1
    assert len(garak_check.parameters["probes"]) == 3
    assert "dan.DanInTheWild" in garak_check.parameters["probes"]


def test_garak_check_is_bounded() -> None:
    check = _garak_check()
    assert check.parameters["prompt_cap"] == 1
    assert check.parameters["timeout_seconds"] == 600
