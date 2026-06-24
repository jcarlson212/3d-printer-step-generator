"""Geometry validation checks for the build loop.

After CAD code executes, we inspect the produced solid and grade it against hard
requirements (must be one valid, watertight, positive-volume solid that fits the
build volume) and soft expectations (roughly the target proportions, stable base).
Failures become the "observation" fed back to the model to revise.
"""

from __future__ import annotations

from pydantic import BaseModel

from .executor import ExecutionResult
from .profiles import MachineProfile
from .prompt import TargetDimensions


class CheckReport(BaseModel):
    errors: list[str] = []  # must be fixed; block acceptance
    warnings: list[str] = []  # acceptable, but the model should improve if it can

    @property
    def passed(self) -> bool:
        return not self.errors

    def as_observation(self) -> str:
        lines: list[str] = []
        if self.errors:
            lines.append("Problems that MUST be fixed:")
            lines.extend(f"- {e}" for e in self.errors)
        if self.warnings:
            lines.append("Improve if reasonable:")
            lines.extend(f"- {w}" for w in self.warnings)
        return "\n".join(lines)


def validate_geometry(
    exec_res: ExecutionResult,
    *,
    target: TargetDimensions,
    machine: MachineProfile,
    height_tol: float = 0.35,
    footprint_tol: float = 0.6,
) -> CheckReport:
    """Grade a successfully-executed solid against requirements."""
    report = CheckReport()

    if exec_res.is_valid is False:
        report.errors.append("The solid is not valid (self-intersecting or non-manifold).")

    if exec_res.n_solids is not None and exec_res.n_solids != 1:
        report.errors.append(
            f"The model must be ONE connected solid, but it has {exec_res.n_solids}. "
            "Fuse the parts (union) into a single watertight body."
        )

    if exec_res.volume_mm3 is not None and exec_res.volume_mm3 <= 0:
        report.errors.append("The solid has zero/negative volume (no real body was produced).")

    bb = exec_res.bbox_mm
    if bb:
        x, y, z = bb
        bv = machine.build_volume
        if not bv.fits(x, y, z):
            report.errors.append(
                f"Bounding box {x:.0f}x{y:.0f}x{z:.0f} mm exceeds the build volume "
                f"{bv.x_mm:.0f}x{bv.y_mm:.0f}x{bv.z_mm:.0f} mm. Scale it down."
            )
        # Soft proportion checks (height is the dominant axis for a chess piece).
        if z > 0:
            if abs(z - target.height_mm) / target.height_mm > height_tol:
                report.warnings.append(
                    f"Height {z:.0f} mm is off the target ~{target.height_mm:.0f} mm; "
                    "adjust toward the target proportion."
                )
        footprint = max(x, y)
        if footprint > target.max_footprint_mm * (1 + footprint_tol):
            report.warnings.append(
                f"Base footprint ~{footprint:.0f} mm is much wider than the target "
                f"~{target.max_footprint_mm:.0f} mm."
            )

    return report
