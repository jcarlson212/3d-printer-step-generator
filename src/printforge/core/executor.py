"""Execute LLM-authored build123d code and export a STEP file.

The model returns parametric CAD code; we run it in a *separate Python process*
(isolation + a hard timeout) with build123d imported, then export the solid bound
to ``result`` to a real ``.step`` file. Because the geometry is produced by the
CAD kernel (OpenCascade), the STEP is guaranteed well-formed -- the model never
hand-writes STEP.

If the optional ``cad`` extra (build123d) isn't installed, execution is skipped
and the caller still gets the CAD code + explanation back.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel

from .prompt import RESULT_VAR

# Runner executed in the child process. It execs the user's CAD code with
# build123d in scope and exports `result` to STEP.
_RUNNER = f"""
import sys

code = open(sys.argv[1]).read()
# Run the model's code in a namespace that already has build123d's names, matching
# the system-prompt contract ("assume `from build123d import *` is already done").
ns = {{}}
exec("from build123d import *", ns)
exec(code, ns)
result = ns.get({RESULT_VAR!r})
if result is None:
    raise SystemExit("CAD code did not define a `{RESULT_VAR}` solid")
from build123d import export_step
export_step(result, sys.argv[2])
# Also export an STL alongside (for the render-in-the-loop refinement stage).
try:
    from build123d import export_stl
    export_stl(result, sys.argv[2].rsplit(".", 1)[0] + ".stl")
except Exception:
    pass

# Geometry diagnostics for the validation stage.
import json as _json
_diag = {{}}
try:
    _solids = result.solids()
    _diag["n_solids"] = len(_solids)
except Exception:
    _diag["n_solids"] = None
try:
    _diag["volume_mm3"] = float(result.volume)
except Exception:
    _diag["volume_mm3"] = None
try:
    _bb = result.bounding_box()
    _diag["bbox_mm"] = [float(_bb.size.X), float(_bb.size.Y), float(_bb.size.Z)]
except Exception:
    _diag["bbox_mm"] = None
try:
    _diag["is_valid"] = bool(result.is_valid())
except Exception:
    _diag["is_valid"] = None
print("DIAG:" + _json.dumps(_diag))
print("OK")
"""


class ExecutionResult(BaseModel):
    ok: bool
    step_path: str | None = None
    step_bytes_len: int | None = None
    stl_path: str | None = None
    skipped: bool = False
    error: str | None = None
    # Geometry diagnostics (populated on success) for the validation stage.
    n_solids: int | None = None
    volume_mm3: float | None = None
    bbox_mm: list[float] | None = None
    is_valid: bool | None = None


def cad_available() -> bool:
    """True if build123d (the 'cad' extra) is importable."""
    try:
        import build123d  # noqa: F401

        return True
    except Exception:
        return False


def execute_to_step(
    cad_code: str,
    out_path: str | Path,
    *,
    timeout_s: int = 120,
) -> ExecutionResult:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not cad_available():
        return ExecutionResult(
            ok=False,
            skipped=True,
            error="build123d not installed; install the 'cad' extra to export STEP. "
            "(`uv sync --extra cad`)",
        )

    with tempfile.TemporaryDirectory() as td:
        runner = Path(td) / "runner.py"
        code_file = Path(td) / "model_code.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        code_file.write_text(cad_code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, str(runner), str(code_file), str(out_path)],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(ok=False, error=f"CAD execution timed out after {timeout_s}s")

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "unknown error").strip()
        # Keep the tail of the traceback -- it's the actionable part.
        return ExecutionResult(ok=False, error=err[-2000:])

    if not out_path.exists():
        return ExecutionResult(ok=False, error="runner finished but no STEP file was written")

    diag: dict = {}
    for line in (proc.stdout or "").splitlines():
        if line.startswith("DIAG:"):
            import json

            try:
                diag = json.loads(line[len("DIAG:") :])
            except ValueError:
                diag = {}
            break

    stl_candidate = out_path.with_suffix(".stl")
    return ExecutionResult(
        ok=True,
        step_path=str(out_path),
        step_bytes_len=out_path.stat().st_size,
        stl_path=str(stl_candidate) if stl_candidate.exists() else None,
        n_solids=diag.get("n_solids"),
        volume_mm3=diag.get("volume_mm3"),
        bbox_mm=diag.get("bbox_mm"),
        is_valid=diag.get("is_valid"),
    )
