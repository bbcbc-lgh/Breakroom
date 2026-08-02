from __future__ import annotations

from dataclasses import dataclass


def relationship_level(score: int) -> str:
    if score <= 20:
        return "陌生"
    if score <= 40:
        return "熟悉"
    if score <= 60:
        return "友好"
    if score <= 80:
        return "亲密"
    return "挚友"


@dataclass(frozen=True, slots=True)
class RelationshipState:
    score: int = 10
    interaction_count: int = 0
    positive_points_today: int = 0
    positive_points_date: str = ""


@dataclass(frozen=True, slots=True)
class RelationshipDecision:
    old_score: int
    new_score: int
    delta: int
    level: str
    rule_id: str
    reason: str
    interaction_count: int
    positive_points_today: int
    positive_points_date: str
