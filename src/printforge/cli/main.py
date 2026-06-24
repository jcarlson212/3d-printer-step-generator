"""Interactive CLI for running the chess-piece workflow locally.

    printforge knight        # interactive: asks questions, validates, runs
    printforge run FILE.json # run a saved request non-interactively
    printforge new FILE.json # build a request interactively and save it (no run)

The interactive flow validates every answer (emails, addresses, numbers) and
re-prompts on bad input, then constructs a validated ChessWorkflowRequest before
running anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import questionary
import typer
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel

from printforge.core.delivery import DEFAULT_RECIPIENT, DeliveryConfig
from printforge.core.executor import cad_available
from printforge.core.order import OrderInfo, ShippingAddress
from printforge.core.providers import Provider, ProviderConfig
from printforge.core.registry import get_machine, resolve_machine_material
from printforge.workflows.chess.engine import run_chess_workflow
from printforge.workflows.chess.models import ChessWorkflowRequest, PieceDimensions
from printforge.workflows.chess.pieces import Color, PieceType
from printforge.workflows.chess.templates import ENABLED_PIECES
from printforge.workflows.chess.themes import PARTHENON_KNIGHT

app = typer.Typer(add_completion=False, help="Agentic 3D-print STEP generator (chess).")
console = Console()


# --------------------------------------------------------------------------- #
# small prompt helpers (validate + re-prompt)
# --------------------------------------------------------------------------- #
def _required_text(label: str, default: str | None = None) -> str:
    val = questionary.text(
        label,
        default=default or "",
        validate=lambda t: True if t.strip() else "Required.",
    ).ask()
    if val is None:
        raise typer.Abort()
    return val.strip()


def _optional_text(label: str, default: str = "") -> str | None:
    val = questionary.text(label, default=default).ask()
    if val is None:
        raise typer.Abort()
    val = val.strip()
    return val or None


def _email(label: str) -> str:
    from pydantic import TypeAdapter
    from pydantic import EmailStr

    adapter = TypeAdapter(EmailStr)

    def _valid(t: str) -> bool | str:
        try:
            adapter.validate_python(t.strip())
            return True
        except ValidationError:
            return "Enter a valid email address."

    val = questionary.text(label, validate=_valid).ask()
    if val is None:
        raise typer.Abort()
    return val.strip()


def _int(label: str, default: int = 1, minimum: int = 1) -> int:
    def _valid(t: str) -> bool | str:
        try:
            return True if int(t) >= minimum else f"Must be >= {minimum}."
        except ValueError:
            return "Enter a whole number."

    val = questionary.text(label, default=str(default), validate=_valid).ask()
    if val is None:
        raise typer.Abort()
    return int(val)


def _select(label: str, choices: list[str], default: str | None = None) -> str:
    val = questionary.select(label, choices=choices, default=default).ask()
    if val is None:
        raise typer.Abort()
    return val


# --------------------------------------------------------------------------- #
# interactive request builder
# --------------------------------------------------------------------------- #
def _build_request_interactive() -> ChessWorkflowRequest:
    console.print(Panel.fit("GarryChess  ::  STEP generator", style="bold cyan"))

    # --- scope ---
    enabled = sorted(p.value for p in ENABLED_PIECES)
    if len(enabled) == 1:
        piece = PieceType(enabled[0])
        console.print(f"Piece: [bold]{enabled[0]}[/bold] (only enabled piece right now)")
    else:
        piece = PieceType(_select("Which piece?", enabled))

    color_choice = _select("Which color?", ["white", "black", "both"], default="white")
    colors = [Color.WHITE, Color.BLACK] if color_choice == "both" else [Color(color_choice)]

    # --- theme ---
    use_parthenon = questionary.confirm(
        "Use the Parthenon-marble knight theme?", default=True
    ).ask()
    if use_parthenon is None:
        raise typer.Abort()
    theme = PARTHENON_KNIGHT if use_parthenon else _optional_text("Custom theme (optional):")

    # --- machine / materials ---
    machine = get_machine(_select("Machine?", sorted([m for m in _machine_keys()]),
                                  default="bambu_a1_mini"))
    mats = questionary.checkbox(
        "Preferred materials (space to toggle):",
        choices=[
            questionary.Choice(k, checked=(k == machine.default_material_key))
            for k in machine.supported_material_keys
        ],
    ).ask()
    if mats is None:
        raise typer.Abort()
    if not mats:
        mats = [machine.default_material_key]

    # --- dimensions ---
    dims = None
    if questionary.confirm(
        "Override standard Staunton dimensions?", default=False
    ).ask():
        h = _optional_text("Height mm (blank = standard):")
        w = _optional_text("Base width mm (blank = standard):")
        dims = PieceDimensions(
            height_mm=float(h) if h else None,
            width_mm=float(w) if w else None,
        )

    # --- provider ---
    provider = _select(
        "Inference provider?",
        ["anthropic", "openai", "lmstudio", "bedrock"],
        default="anthropic",
    )
    api_key = base_url = aws_region = None
    if provider in ("anthropic", "openai"):
        api_key = _optional_text(f"{provider} API key (blank = use env):")
    elif provider == "lmstudio":
        base_url = _optional_text("LM Studio base URL:", "http://localhost:1234/v1")
        api_key = _optional_text("LM Studio model name (blank = default):")
    elif provider == "bedrock":
        aws_region = _optional_text("AWS region:", "us-east-1")
    provider_cfg = ProviderConfig(
        provider=Provider(provider),
        api_key=api_key if provider != "lmstudio" else None,
        model=api_key if provider == "lmstudio" and api_key else None,
        base_url=base_url,
        aws_region=aws_region,
    )

    # --- order ---
    console.print("\n[bold]Order details[/bold]")
    first = _required_text("First name:")
    last = _required_text("Last name:")
    email = _email("Email:")
    line1 = _required_text("Address line 1:")
    line2 = _optional_text("Address line 2 (optional):")
    city = _required_text("City:")
    state = _optional_text("State/Province (optional):")
    postal = _required_text("Postal code:")
    country = _required_text("Country:", "US")
    phone = _optional_text("Phone (optional):")
    quantity = _int("Quantity:", default=1)
    stripe = _optional_text("Stripe payment link (optional):")
    deadline = _optional_text("Requested-by / deadline (optional):")
    notes = _optional_text("Order notes (optional):")

    order = OrderInfo(
        first_name=first, last_name=last, email=email,
        shipping_address=ShippingAddress(
            line1=line1, line2=line2, city=city,
            state_province=state, postal_code=postal, country=country,
        ),
        phone=phone, quantity=quantity, stripe_payment_link=stripe,
        deadline=deadline, notes=notes,
    )

    # --- delivery ---
    recipient = _optional_text("Deliver STEP to email:", DEFAULT_RECIPIENT) or DEFAULT_RECIPIENT

    export = True
    if not cad_available():
        console.print(
            "[yellow]build123d not installed; STEP export will be skipped "
            "(install the 'cad' extra). The CAD code + explanation are still produced.[/yellow]"
        )
        export = questionary.confirm("Continue without STEP export?", default=True).ask() or False
        if not export:
            raise typer.Abort()
        export = False

    return ChessWorkflowRequest(
        order=order,
        colors=colors,
        pieces=[piece],
        theme=theme,
        dimensions=dims,
        machine_key=machine.key,
        preferred_materials=mats,
        provider=provider_cfg,
        delivery=DeliveryConfig(recipient=recipient),
        export_step=export,
    )


def _machine_keys() -> list[str]:
    from printforge.core.registry import MACHINES

    return list(MACHINES.keys())


def _confirm_and_run(request: ChessWorkflowRequest) -> None:
    console.print(Panel("\n".join(request.order.summary_lines()), title="Order", style="cyan"))
    machine, material = resolve_machine_material(request.machine_key, request.material_key)
    console.print(
        f"[bold]Run:[/bold] {[ (c.value,p.value) for c,p in request.work_units() ]} "
        f"on {machine.name} / {material.name} via {request.provider.provider.value} "
        f"({request.provider.model})"
    )
    if not questionary.confirm("Generate now?", default=True).ask():
        console.print("Aborted before running.")
        raise typer.Abort()

    result = run_chess_workflow(request, progress=lambda m: console.print(f"  {m}"))
    if result.ok:
        console.print(Panel(f"Done. {result.delivery_detail}", style="green"))
    else:
        errs = [f"{a.color.value} {a.piece.value}: {a.error}" for a in result.artifacts if a.error]
        console.print(Panel("Completed with issues:\n" + "\n".join(errs), style="yellow"))


@app.command()
def knight() -> None:
    """Interactively build and run a knight request."""
    request = _build_request_interactive()
    _confirm_and_run(request)


@app.command()
def new(output: Path = typer.Argument(..., help="Where to save the request JSON.")) -> None:
    """Interactively build a request and save it to JSON (does not run)."""
    request = _build_request_interactive()
    output.write_text(request.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"Saved request to [bold]{output}[/bold]")


@app.command()
def run(
    request_file: Path = typer.Argument(..., help="Path to a request JSON file."),
    no_email: bool = typer.Option(False, "--no-email", help="Skip delivery."),
) -> None:
    """Run a saved request non-interactively."""
    data = json.loads(request_file.read_text(encoding="utf-8"))
    try:
        request = ChessWorkflowRequest.model_validate(data)
    except ValidationError as e:
        console.print(Panel(str(e), title="Invalid request", style="red"))
        raise typer.Exit(1) from None
    result = run_chess_workflow(
        request, progress=lambda m: console.print(f"  {m}"), send_email=not no_email
    )
    console.print(f"order {result.order_id}: ok={result.ok} {result.delivery_detail or ''}")


if __name__ == "__main__":
    app()
