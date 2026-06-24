"""Chess-piece workflow engine.

Flow:
1. Resolve which (color, piece) units are in scope from the request.
2. Generate them one at a time. Each step receives the prior steps' STEP files
   and detailed_explanations so the set stays visually consistent.
3. Execute each step's CAD code to a real STEP file (when enabled/available).
4. Email the finished STEP file(s) to the customer, with the concatenated
   detailed_explanations as the body.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from printforge.core.build_loop import build_piece
from printforge.core.delivery import Attachment, deliver
from printforge.core.prompt import PriorPieceContext
from printforge.core.registry import resolve_machine_material

from .models import ChessWorkflowRequest, PieceArtifact, WorkflowResult
from .templates import get_template

# Optional progress callback: (message) -> None.
Progress = Callable[[str], None]


def _noop(_: str) -> None:  # pragma: no cover - trivial
    pass


def _step_filename(color: str, piece: str) -> str:
    return f"{color}_{piece}.step"


def _build_email_body(request: ChessWorkflowRequest, artifacts: list[PieceArtifact]) -> str:
    """Order summary + concatenated detailed explanations for all pieces."""
    parts: list[str] = []
    parts.append(f"New chess piece order for {request.order.customer_name}.")
    parts.append("")
    parts.extend(request.order.summary_lines())
    parts.append("")
    machine, material = resolve_machine_material(request.machine_key, request.material_key)
    parts.append(f"Machine:   {machine.name}")
    preferred = ", ".join(request.preferred_materials)
    parts.append(f"Material:  {material.name}  (preferred: {preferred})")
    if request.theme:
        parts.append("")
        parts.append("Theme:")
        parts.append(request.theme.strip())
    parts.append("")
    parts.append("=" * 70)
    parts.append("PER-PIECE DETAILS")
    parts.append("=" * 70)
    for a in artifacts:
        parts.append("")
        parts.append(f"--- {a.color.value} {a.piece.value} "
                     f"({a.step_filename or 'no STEP exported'}) ---")
        if a.error:
            parts.append(f"[!] STEP export issue: {a.error}")
        parts.append("")
        parts.append(a.detailed_explanation.strip())
    return "\n".join(parts)


def run_chess_workflow(
    request: ChessWorkflowRequest,
    *,
    out_dir: str | Path = "out",
    progress: Progress | None = None,
    send_email: bool = True,
) -> WorkflowResult:
    say = progress or _noop
    machine, material = resolve_machine_material(request.machine_key, request.material_key)
    order_dir = Path(out_dir) / request.order.order_id
    order_dir.mkdir(parents=True, exist_ok=True)

    units = request.work_units()
    say(f"Scope: {len(units)} piece(s) -> " +
        ", ".join(f"{c.value} {p.value}" for c, p in units))

    # Customer personalization derived from the order, injected into every prompt.
    personalization: list[str] = []
    if request.order.filament_shade:
        personalization.append(
            f"This will print in '{request.order.filament_shade}' filament -- lean the "
            "surface treatment and detail toward that look."
        )
    if request.order.engraving_message:
        personalization.append(
            f"Engrave the text '{request.order.engraving_message}' on the base as a "
            "shallow recessed inscription, sized at or above the printer's min feature "
            "so it resolves cleanly."
        )

    # Reference images (rendered from STLs and/or provided files) for vision models.
    reference_images: list[bytes] = []
    if request.use_vision:
        from printforge.core.vision import render_references

        reference_images = render_references(
            stl_dir=request.reference_stl_dir,
            image_paths=request.reference_images,
            max_images=request.max_reference_images,
        )
        say(f"Vision: {len(reference_images)} reference image(s) prepared.")

    artifacts: list[PieceArtifact] = []
    prior: list[PriorPieceContext] = []

    for idx, (color, piece) in enumerate(units, start=1):
        say(f"[{idx}/{len(units)}] Building {color.value} {piece.value}...")
        template = get_template(piece)
        target = request.target_for(piece)
        gotchas = request.gotchas_for(piece)
        step_path = order_dir / _step_filename(color.value, piece.value)

        # ReAct-style build loop: generate -> execute -> validate -> revise -> ...
        outcome = build_piece(
            template,
            provider_cfg=request.provider,
            machine=machine,
            material=material,
            color=color.value,
            theme=request.theme,
            target=target,
            gotchas=gotchas,
            out_path=step_path,
            prior=prior,
            personalization=personalization or None,
            reference_images=reference_images or None,
            max_iters=request.max_repairs + 1,
            progress=lambda m: say(f"      {m}"),
        )
        gen = outcome.generation

        artifact = PieceArtifact(
            color=color,
            piece=piece,
            cad_code=gen.cad_code,
            detailed_explanation=gen.detailed_explanation,
            stages=len(outcome.stages),
            warnings=outcome.report.warnings,
        )
        if outcome.execution.ok:
            artifact.step_filename = _step_filename(color.value, piece.value)
            artifact.step_path = outcome.execution.step_path
            artifact.step_bytes_len = outcome.execution.step_bytes_len
            if outcome.ok:
                say(f"      STEP written ({outcome.execution.step_bytes_len} bytes), "
                    f"checks passed in {len(outcome.stages)} iteration(s).")
            else:
                say(f"      STEP written but {len(outcome.report.warnings)} warning(s) remain.")
        elif not outcome.execution.skipped:
            artifact.error = outcome.execution.error
            say(f"      STEP not exported after {len(outcome.stages)} iteration(s).")

        # Persist the final code + explanation for traceability.
        stem = f"{color.value}_{piece.value}"
        (order_dir / f"{stem}.py").write_text(artifact.cad_code, encoding="utf-8")
        (order_dir / f"{stem}.explanation.md").write_text(
            artifact.detailed_explanation, encoding="utf-8"
        )

        artifacts.append(artifact)
        prior.append(
            PriorPieceContext(
                slug=piece.value,
                color=color.value,
                detailed_explanation=gen.detailed_explanation,
                cad_code=gen.cad_code,
                step_filename=artifact.step_filename,
            )
        )

    result = WorkflowResult(order_id=request.order.order_id, artifacts=artifacts)

    if send_email:
        body = _build_email_body(request, artifacts)
        (order_dir / "delivery_email.txt").write_text(body, encoding="utf-8")
        attachments = [
            Attachment(filename=a.step_filename, content=Path(a.step_path).read_bytes())
            for a in artifacts
            if a.step_path and a.step_filename
        ]
        piece_desc = ", ".join(f"{a.color.value} {a.piece.value}" for a in artifacts)
        subject = f"[{request.order.order_id}] Chess STEP files: {piece_desc}"
        say(f"Delivering to {request.delivery.recipient}...")
        # Delivery must not sink a successful generation (e.g. SES not yet verified):
        # the STEP + explanation are already on disk; record the failure and move on.
        try:
            delivery = deliver(
                request.delivery, subject=subject, body=body, attachments=attachments
            )
            result.delivery_detail = delivery.detail
            say(f"Delivery: {delivery.detail}")
        except Exception as e:
            result.delivery_detail = f"delivery failed: {e}"
            say(f"Delivery FAILED (generation still succeeded): {e}")

    return result
