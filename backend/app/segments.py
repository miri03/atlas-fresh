"""Quality segments and the quality order used across the planning policy.

Quality order: A is the highest quality, followed by B, C, then D.
A lower numeric rank means higher quality.
"""

from __future__ import annotations

from typing import Final

SEGMENTS: Final[list[str]] = ["A", "B", "C", "D"]
RANKS: Final[dict[str, int]] = {"A": 0, "B": 1, "C": 2, "D": 3}
VALID_MODES: Final[set[str]] = {"EXACT", "MINIMUM"}


def rank(segment: str) -> int:
    return RANKS[segment]


def is_valid_segment(segment: str) -> bool:
    return segment in RANKS


def upgrade_distance(requested: str, supplied: str) -> int:
    """Quality levels above the client's requested segment.

    0 means the supply segment is exactly the requested one. Positive
    values mean the supply is *better* than requested (client gets a
    quality upgrade). Negative values are illegal (quality downgrade).
    """
    return rank(requested) - rank(supplied)


def compatible_segments(mode: str, requested: str) -> list[str]:
    """Ordered list of segments a client accepts, exact match first.

    * EXACT: only the requested segment.
    * MINIMUM: the requested segment or a better one, following the
      'prefer the requested segment before a better one' rule, i.e.
      C before B before A for a MINIMUM C client.
    """
    if mode == "EXACT":
        return [requested]
    ranked = sorted(RANKS.keys(), key=RANKS.__getitem__)
    better = [s for s in ranked if RANKS[s] < RANKS[requested]]
    return [requested] + better