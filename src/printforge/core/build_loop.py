"""ReAct-style build loop for one piece.

Rather than one-shot generation, each piece runs through iterative stages with
checks between them:

    generate ->[execute]-> inspect geometry (validate) ->[reflect]-> revise -> ...

Each iteration is a thought/action/observation step: the action is CAD code, the
observation is the execution result plus geometry checks, and the reflection feeds
those back to the model to revise. The loop stops when the solid executes AND
passes the hard checks, or when the iteration budget is exhausted.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from .agent import (
    CadGeneration,
    generate_piece,
    refine_piece,
    revise_piece,
    safety_review,
)
from .executor import ExecutionResult, cad_available, execute_to_step
from .profiles import MachineProfile, MaterialProfile
from .prompt import BasePieceTemplate, PriorPieceContext, TargetDimensions
from .providers import ProviderConfig
from .validation import CheckReport, validate_geometry


class BuildStage(BaseModel):
    """One iteration's outcome, for traceability."""

    iteration: int
    executed: bool
    passed: bool
    errors: list[str] = []
    warnings: list[str] = []


class BuildOutcome(BaseModel):
    generation: CadGeneration
    execution: ExecutionResult
    report: CheckReport
    stages: list[BuildStage] = []

    @property
    def ok(self) -> bool:
        return self.execution.ok and self.report.passed


def build_piece(
    template: BasePieceTemplate,
    *,
    provider_cfg: ProviderConfig,
    machine: MachineProfile,
    material: MaterialProfile,
    color: str,
    theme: str | None,
    target: TargetDimensions,
    gotchas: list[str],
    out_path: str | Path,
    prior: list[PriorPieceContext] | None = None,
    personalization: list[str] | None = None,
    reference_images: list[bytes] | None = None,
    max_iters: int = 3,
    refine_rounds: int = 0,
    safety_rounds: int = 0,
    progress=lambda _m: None,
) -> BuildOutcome:
    # The full original brief (theme, styling, gotchas, constraints) -- threaded into
    # every revision so the loop never drifts away from the aesthetic.
    brief = template.user_prompt(
        machine=machine,
        material=material,
        color=color,
        theme=theme,
        target=target,
        gotchas=gotchas,
        prior=prior,
        personalization=personalization,
    )

    gen = generate_piece(
        template,
        provider_cfg=provider_cfg,
        machine=machine,
        material=material,
        color=color,
        theme=theme,
        target=target,
        gotchas=gotchas,
        prior=prior,
        personalization=personalization,
        reference_images=reference_images,
    )

    # No CAD runtime: return the generation un-executed (caller handles).
    if not cad_available():
        exec_res = execute_to_step(gen.cad_code, out_path)  # returns skipped=True
        return BuildOutcome(generation=gen, execution=exec_res, report=CheckReport())

    stages: list[BuildStage] = []
    exec_res = ExecutionResult(ok=False)
    report = CheckReport()

    for i in range(max_iters):
        progress(f"iteration {i + 1}/{max_iters}: executing + checking")
        exec_res = execute_to_step(gen.cad_code, out_path)

        if exec_res.ok:
            report = validate_geometry(exec_res, target=target, machine=machine)
        else:
            report = CheckReport(errors=[exec_res.error or "execution failed"])

        stages.append(
            BuildStage(
                iteration=i + 1,
                executed=exec_res.ok,
                passed=exec_res.ok and report.passed,
                errors=report.errors,
                warnings=report.warnings,
            )
        )

        if exec_res.ok and report.passed:
            progress(f"iteration {i + 1}: passed all checks")
            break

        if i < max_iters - 1:
            short = (report.errors[:1] or report.warnings[:1] or ["revising"])[0]
            progress(f"iteration {i + 1}: revising -> {short[:120]}")
            gen = revise_piece(
                template,
                provider_cfg=provider_cfg,
                prev_code=gen.cad_code,
                observation=report.as_observation(),
                executed=exec_res.ok,
                original_brief=brief,
                reference_images=reference_images,
            )

    # Aesthetic refinement: once geometrically valid, spend rounds ELEVATING the design
    # by showing the model a render of its own output and asking it to make it less basic
    # / more sculptural. Never regress: only accept a refinement that stays valid.
    if exec_res.ok and report.passed and refine_rounds > 0:
        from .vision import render_solid_views

        for r in range(refine_rounds):
            imgs = render_solid_views(exec_res.stl_path) if exec_res.stl_path else []
            if not imgs:
                break
            progress(f"refine {r + 1}/{refine_rounds}: elevating the design")
            cand = refine_piece(
                template,
                provider_cfg=provider_cfg,
                prev_code=gen.cad_code,
                render_images=imgs,
                original_brief=brief,
                round_num=r + 1,
                rounds_total=refine_rounds,
                reference_images=reference_images,
            )
            cand_res = execute_to_step(cand.cad_code, out_path)
            cand_report = (
                validate_geometry(cand_res, target=target, machine=machine)
                if cand_res.ok
                else CheckReport(errors=[cand_res.error or "execution failed"])
            )
            accepted = cand_res.ok and cand_report.passed
            stages.append(
                BuildStage(
                    iteration=len(stages) + 1,
                    executed=cand_res.ok,
                    passed=accepted,
                    errors=cand_report.errors,
                    warnings=cand_report.warnings,
                )
            )
            if accepted:
                gen, exec_res, report = cand, cand_res, cand_report
            else:
                progress(f"refine {r + 1}: rejected (would regress); keeping prior valid solid")
                break

    # Final packaging/durability safety gate: review the finished piece for ship
    # safety; if unsafe, revise with the issue explanation threaded in and re-check.
    if exec_res.ok and report.passed and safety_rounds > 0:
        from .vision import render_solid_views

        for s in range(safety_rounds):
            imgs = render_solid_views(exec_res.stl_path) if exec_res.stl_path else []
            verdict = safety_review(
                template,
                provider_cfg=provider_cfg,
                cad_code=gen.cad_code,
                render_images=imgs,
                material=material,
                machine=machine,
            )
            if verdict.ok:
                progress(f"safety check {s + 1}: ship-safe")
                break
            issues = "PACKAGING/DURABILITY ISSUES FOUND (fix these, keep the design):\n- " + (
                "\n- ".join(verdict.issues)
            )
            progress(f"safety check {s + 1}: not ship-safe -> revising ({len(verdict.issues)} issues)")
            cand = revise_piece(
                template,
                provider_cfg=provider_cfg,
                prev_code=gen.cad_code,
                observation=issues,
                executed=True,
                original_brief=brief,
                reference_images=reference_images,
            )
            cand_res = execute_to_step(cand.cad_code, out_path)
            cand_report = (
                validate_geometry(cand_res, target=target, machine=machine)
                if cand_res.ok
                else CheckReport(errors=[cand_res.error or "execution failed"])
            )
            stages.append(
                BuildStage(
                    iteration=len(stages) + 1,
                    executed=cand_res.ok,
                    passed=cand_res.ok and cand_report.passed,
                    errors=cand_report.errors,
                    warnings=["safety: " + i for i in verdict.issues],
                )
            )
            if cand_res.ok and cand_report.passed:
                gen, exec_res, report = cand, cand_res, cand_report
            else:
                progress(f"safety revise {s + 1}: rejected (would regress); keeping prior solid")
                break

    return BuildOutcome(generation=gen, execution=exec_res, report=report, stages=stages)
