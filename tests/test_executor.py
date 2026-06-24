"""Executor tests. The CAD path is skipped when the 'cad' extra isn't installed."""

from __future__ import annotations

from pathlib import Path

import pytest

from printforge.core.executor import cad_available, execute_to_step

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "steps" / "knight_example.py"


def test_skips_cleanly_without_build123d(tmp_path, monkeypatch):
    import printforge.core.executor as ex

    monkeypatch.setattr(ex, "cad_available", lambda: False)
    res = ex.execute_to_step("result = None", tmp_path / "x.step")
    assert res.skipped is True
    assert res.ok is False


@pytest.mark.skipif(not cad_available(), reason="build123d (cad extra) not installed")
def test_example_code_exports_valid_step(tmp_path):
    code = EXAMPLE.read_text()
    out = tmp_path / "knight.step"
    res = execute_to_step(code, out)
    assert res.ok, res.error
    assert out.exists() and out.stat().st_size > 1000
    assert out.read_text(errors="ignore").startswith("ISO-10303-21;")


@pytest.mark.skipif(not cad_available(), reason="build123d (cad extra) not installed")
def test_missing_result_var_is_an_error(tmp_path):
    res = execute_to_step("x = 1  # no `result`", tmp_path / "x.step")
    assert res.ok is False
    assert "result" in (res.error or "").lower()
