"""The CAD-generation agent.

Wraps a pydantic-ai ``Agent`` with structured output so every step reliably
returns CAD code plus a thorough explanation -- no markdown parsing, the model is
forced to fill the schema and retries on mismatch.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from .profiles import MachineProfile, MaterialProfile
from .prompt import BasePieceTemplate, PriorPieceContext, TargetDimensions
from .providers import ProviderConfig, build_model


class CadGeneration(BaseModel):
    """Structured result of one generation step."""

    cad_code: str = Field(
        description="Complete build123d Python code assigning the final solid to `result`."
    )
    detailed_explanation: str = Field(
        description="Thorough rationale: form decisions, exact parameters, how each "
        "printability gotcha was handled, and guidance for set consistency."
    )


def generate_piece(
    template: BasePieceTemplate,
    *,
    provider_cfg: ProviderConfig,
    machine: MachineProfile,
    material: MaterialProfile,
    color: str,
    theme: str | None,
    target: TargetDimensions,
    gotchas: list[str],
    prior: list[PriorPieceContext] | None = None,
    personalization: list[str] | None = None,
    reference_images: list[bytes] | None = None,
) -> CadGeneration:
    """Run one generation step and return structured CAD + explanation.

    If ``reference_images`` are supplied (e.g. rendered views of reference STLs)
    they are sent alongside the text prompt for vision-capable models.
    """
    model = build_model(provider_cfg)
    agent = Agent(
        model,
        output_type=CadGeneration,
        system_prompt=template.system_prompt(),
    )
    user_prompt = template.user_prompt(
        machine=machine,
        material=material,
        color=color,
        theme=theme,
        target=target,
        gotchas=gotchas,
        prior=prior,
        personalization=personalization,
    )

    prompt_input: list[object] = [user_prompt]
    if reference_images:
        from pydantic_ai import BinaryContent

        prompt_input.append(
            "Reference images of existing physical knight pieces (for silhouette / "
            "proportion / styling inspiration -- do not copy exactly):"
        )
        for img in reference_images:
            prompt_input.append(BinaryContent(data=img, media_type="image/png"))

    result = agent.run_sync(prompt_input if reference_images else user_prompt)
    return result.output
