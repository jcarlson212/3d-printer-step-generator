"""Chess domain enums and standard (Staunton) sizing."""

from __future__ import annotations

from enum import Enum


class Color(str, Enum):
    WHITE = "white"
    BLACK = "black"


class PieceType(str, Enum):
    PAWN = "pawn"
    KNIGHT = "knight"
    BISHOP = "bishop"
    ROOK = "rook"
    QUEEN = "queen"
    KING = "king"


# Standard tournament (Staunton) proportions in mm: (height, max base footprint).
# Used as the default target when a request doesn't specify dimensions. These are
# also surfaced in the prompt for local runs as "standard chess size".
STANDARD_SIZE_MM: dict[PieceType, tuple[float, float]] = {
    PieceType.KING: (95.0, 40.0),
    PieceType.QUEEN: (85.0, 38.0),
    PieceType.BISHOP: (70.0, 33.0),
    PieceType.KNIGHT: (60.0, 33.0),
    PieceType.ROOK: (50.0, 32.0),
    PieceType.PAWN: (45.0, 28.0),
}

# A full set per color (counts) -- here for future full-set workflows.
SET_COUNTS: dict[PieceType, int] = {
    PieceType.PAWN: 8,
    PieceType.KNIGHT: 2,
    PieceType.BISHOP: 2,
    PieceType.ROOK: 2,
    PieceType.QUEEN: 1,
    PieceType.KING: 1,
}
