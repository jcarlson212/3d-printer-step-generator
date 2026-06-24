"""Chess piece prompt templates.

``ChessPieceTemplate`` inherits the shared :class:`BasePieceTemplate` and adds
chess-wide conventions (Staunton base, weighted feel, set consistency). Each
concrete piece (``KnightTemplate`` ...) inherits that and supplies form-specific
design guidance + default printing gotchas.

Only the pieces listed in :data:`ENABLED_PIECES` can actually run today; the rest
are defined so the full-set workflow is a small step away.
"""

from __future__ import annotations

from printforge.core.prompt import BasePieceTemplate, TargetDimensions

from .pieces import STANDARD_SIZE_MM, PieceType


def _std(piece: PieceType) -> TargetDimensions:
    h, w = STANDARD_SIZE_MM[piece]
    return TargetDimensions(height_mm=h, max_footprint_mm=w)


class ChessPieceTemplate(BasePieceTemplate):
    """Common behavior shared by every chess piece template."""

    # Reference docs injected into every chess piece's system prompt. The CAD
    # masterclass (deep craft + per-piece recipes) is always present.
    resource_keys: list[str] = ["cad_masterclass", "build123d", "fdm_pla", "step_stl"]

    def system_prompt(self) -> str:
        return super().system_prompt() + (
            "\n\nChess-set conventions:\n"
            "- Follow Staunton proportions unless the brief says otherwise.\n"
            "- The base must be a clean, flat, circular disc that sits flush on the "
            "build plate (this is also the natural print orientation -- no raft of supports "
            "under the whole piece).\n"
            "- Leave a shallow recess option under the base for an adhesive felt pad; "
            "do not model the felt.\n"
            "- The piece should read clearly as its type from across a board.\n"
            "- Keep one consistent base diameter family across a set so pieces look related.\n"
        )


class PawnTemplate(ChessPieceTemplate):
    slug: str = "pawn"
    display_name: str = "Pawn"
    design_brief: str = (
        "A classic Staunton pawn: a round ball finial on a collared, tapering stem "
        "rising from a domed circular base."
    )
    default_gotchas: list[str] = [
        "The neck under the ball is the thinnest section; keep it above the min wall.",
        "The spherical top prints cleanly only near the poles -- a small flat or "
        "slight ogive at the very top avoids a rough tip.",
    ]
    default_target: TargetDimensions = _std(PieceType.PAWN)


class KnightTemplate(ChessPieceTemplate):
    slug: str = "knight"
    display_name: str = "Knight"
    resource_keys: list[str] = [
        "cad_masterclass", "build123d", "fdm_pla", "step_stl", "knight_guide",
    ]
    design_brief: str = (
        "A Staunton knight: a stylised horse's head and arched neck rising from a "
        "collared circular base. The standard tournament knight descends from a horse "
        "of the Parthenon frieze (one of Selene's horses, the Elgin Marbles), so the "
        "form is classical sculpture, not a cartoon horse.\n"
        "Anatomy to capture: a strong arched crest of the neck, a defined jaw and "
        "muzzle angled slightly down/forward, flared nostrils, carved mane along the "
        "crest, and alert ears. Aim for a noble, sculptural profile readable in "
        "silhouette."
    )
    default_gotchas: list[str] = [
        "The muzzle projects forward and creates a steep front overhang -- angle the "
        "head so the underside of the jaw stays within the overhang limit, or keep the "
        "projection short; a long horizontal muzzle needs supports on the most visible face.",
        "Ears and the mane crest are thin, pointed features -- give them at least the "
        "min wall thickness and avoid needle-thin tips that snap when removing supports.",
        "Deep undercuts beneath the jaw and behind the neck leave support scars on "
        "show faces -- blend them with fillets and keep undercuts shallow.",
        # --- shipping/durability emphasis (knight is the most fragile piece) ---
        "Make the base slightly wider than strict Staunton proportion -- it lowers the "
        "centre of gravity, reduces tipping, and protects against breakage in transit.",
        "Avoid thin swords, antennas, weapons, or extended arms on the piece unless they "
        "are designed as a separate detachable part; thin protrusions are the first thing "
        "to snap in shipping.",
        "Reinforce the neck: it is the load-bearing cross-section under a forward-heavy "
        "head and the #1 failure point in shipping. Keep it generously thick; do not "
        "neck it down for looks.",
        "Prefer a robust, near-monolithic body. If detail demands it, a two-piece design "
        "(body + base / weighted insert that join after printing) reduces failure points "
        "and makes the piece easier and safer to pack.",
    ]
    default_target: TargetDimensions = _std(PieceType.KNIGHT)


class BishopTemplate(ChessPieceTemplate):
    slug: str = "bishop"
    display_name: str = "Bishop"
    design_brief: str = (
        "A Staunton bishop: a tall tapering body topped by a mitre with the "
        "characteristic diagonal slit, a bead finial above, on a collared circular base."
    )
    default_gotchas: list[str] = [
        "The mitre slit is a fine cut -- keep it wider than the nozzle so it resolves.",
        "The top bead finial is a small overhang transition; a gentle ogive avoids stringing.",
    ]
    default_target: TargetDimensions = _std(PieceType.BISHOP)


class RookTemplate(ChessPieceTemplate):
    slug: str = "rook"
    display_name: str = "Rook"
    design_brief: str = (
        "A Staunton rook: a cylindrical castle tower with a crenellated (battlement) "
        "top and a collared circular base."
    )
    default_gotchas: list[str] = [
        "The crenellations are small repeated features -- keep gaps wider than the "
        "nozzle and merlons above the min wall.",
        "The hollow between crenellations can leave a small bridge -- keep it short.",
    ]
    default_target: TargetDimensions = _std(PieceType.ROOK)


class QueenTemplate(ChessPieceTemplate):
    slug: str = "queen"
    display_name: str = "Queen"
    design_brief: str = (
        "A Staunton queen: a tall elegant body with a coronet of points beneath a "
        "ball finial, on a wide collared circular base."
    )
    default_gotchas: list[str] = [
        "The coronet points are thin and outward-leaning -- mind overhang and fragility.",
        "Tall and slender: keep the base wide enough for stability on a moving bed.",
    ]
    default_target: TargetDimensions = _std(PieceType.QUEEN)


class KingTemplate(ChessPieceTemplate):
    slug: str = "king"
    display_name: str = "King"
    design_brief: str = (
        "A Staunton king: the tallest piece, a stately body topped by a cross "
        "(cross patee) finial, on a wide collared circular base."
    )
    default_gotchas: list[str] = [
        "The cross finial has thin arms with overhangs -- thicken arms to the min wall "
        "and keep arm overhangs short or chamfered.",
        "Tallest piece: widest base for stability; watch the height/width ratio on a "
        "moving-bed printer.",
    ]
    default_target: TargetDimensions = _std(PieceType.KING)


# Registry: piece type -> template instance.
TEMPLATES: dict[PieceType, ChessPieceTemplate] = {
    PieceType.PAWN: PawnTemplate(),
    PieceType.KNIGHT: KnightTemplate(),
    PieceType.BISHOP: BishopTemplate(),
    PieceType.ROOK: RookTemplate(),
    PieceType.QUEEN: QueenTemplate(),
    PieceType.KING: KingTemplate(),
}

# Configurable scope: only these piece types may run in the current workflow.
# Today: knight only. Add piece types here to enable the full-set workflow.
ENABLED_PIECES: set[PieceType] = {PieceType.KNIGHT}


def get_template(piece: PieceType) -> ChessPieceTemplate:
    return TEMPLATES[piece]
