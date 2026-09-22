"""CLI smoke tests with --dry-run (no FMP key required)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from beauty_bt.cli import app

ROOT = Path(__file__).resolve().parents[1]
MINI_CSV = Path(__file__).resolve().parent / "fixtures" / "mini_flips.csv"
SAMPLE_PRICES = ROOT / "beauty_bt" / "fixtures" / "sample_prices.json"

runner = CliRunner()


def test_cli_flips_dry_run_fixture():
    result = runner.invoke(
        app,
        [
            "flips",
            "--input",
            str(MINI_CSV),
            "--hold",
            "5,10",
            "--fixture",
            str(SAMPLE_PRICES),
            "--no-show-tickers",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "beauty-bt M/V flip backtest" in result.output
    assert "M hold=5" in result.output
    assert "V hold=5" in result.output


def test_cli_missing_key_without_dry_run():
    result = runner.invoke(
        app,
        ["flips", "--input", str(MINI_CSV), "--hold", "5"],
        env={"FMP_API_KEY": ""},
    )
    assert result.exit_code == 2
    assert "FMP_API_KEY" in result.output


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == "0.1.0"
