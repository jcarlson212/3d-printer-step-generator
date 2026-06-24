"""Reusable creative themes for chess pieces.

These are defaults the CLI/examples can offer; any request can supply its own
``theme`` string instead.
"""

PARTHENON_KNIGHT = (
    "The Staunton knight's secret origin. The standard tournament knight is modeled "
    "on a horse from the Parthenon frieze -- one of Selene's horses from the Elgin "
    "Marbles. Almost nobody who plays knows their chess piece is a 2,500-year-old "
    "Greek sculpture. Lean into that: weathered marble texture, the broken classical "
    "profile, the feeling of 'you've been holding a fragment of the Parthenon this "
    "whole time.' Aim it at a higher-end print or a framed presentation piece -- it "
    "sells on the story. Keep the sculptural, noble horse-head silhouette; suggest "
    "eroded stone and a chipped/fractured edge rather than smooth modern plastic."
)

THEMES: dict[str, str] = {
    "parthenon": PARTHENON_KNIGHT,
}
