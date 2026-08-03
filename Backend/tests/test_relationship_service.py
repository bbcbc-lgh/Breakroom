from datetime import date

import pytest

from CyberTown.Domain.Relationship import RelationshipState, relationship_level
from CyberTown.Service.RelationshipService import RelationshipService


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0, "陌生"), (20, "陌生"), (21, "熟悉"), (40, "熟悉"), (41, "友好"),
     (60, "友好"), (61, "亲密"), (80, "亲密"), (81, "挚友"), (100, "挚友")],
)
def test_relationship_level_boundaries(score: int, expected: str) -> None:
    assert relationship_level(score) == expected


def test_positive_tags_are_capped_per_turn() -> None:
    decision = RelationshipService().decide(
        state=RelationshipState(),
        interaction_tags=frozenset({"helpful", "respectful", "curious"}),
        message="谢谢，请给我建议",
        recent_messages=[],
        today=date(2026, 8, 2),
        degraded=False,
    )

    assert decision.delta == 4
    assert decision.new_score == 14


def test_repeat_message_does_not_add_relationship() -> None:
    decision = RelationshipService().decide(
        state=RelationshipState(score=14, interaction_count=1),
        interaction_tags=frozenset({"respectful"}),
        message=" 谢谢 ！",
        recent_messages=["谢谢！"],
        today=date(2026, 8, 2),
        degraded=False,
    )

    assert decision.delta == 0
    assert decision.rule_id == "REL_REPEAT"


def test_daily_positive_cap_is_enforced() -> None:
    decision = RelationshipService().decide(
        state=RelationshipState(
            score=22,
            interaction_count=4,
            positive_points_today=12,
            positive_points_date="2026-08-02",
        ),
        interaction_tags=frozenset({"helpful"}),
        message="请继续",
        recent_messages=[],
        today=date(2026, 8, 2),
        degraded=False,
    )

    assert decision.delta == 0
    assert decision.rule_id == "REL_DAILY_CAP"


def test_daily_positive_cap_resets_on_new_local_day() -> None:
    decision = RelationshipService().decide(
        state=RelationshipState(
            score=22,
            interaction_count=4,
            positive_points_today=12,
            positive_points_date="2026-08-01",
        ),
        interaction_tags=frozenset({"helpful"}),
        message="请继续",
        recent_messages=[],
        today=date(2026, 8, 2),
        degraded=False,
    )

    assert decision.delta == 3
    assert decision.positive_points_today == 3


@pytest.mark.parametrize(
    ("tags", "expected"),
    [(frozenset({"rude"}), -4), (frozenset({"hostile"}), -6)],
)
def test_negative_tags_reduce_relationship(tags: frozenset[str], expected: int) -> None:
    decision = RelationshipService().decide(
        state=RelationshipState(score=50),
        interaction_tags=tags,
        message="负向文本",
        recent_messages=[],
        today=date(2026, 8, 2),
        degraded=False,
    )

    assert decision.delta == expected


def test_fallback_never_changes_relationship() -> None:
    decision = RelationshipService().decide(
        state=RelationshipState(score=30),
        interaction_tags=frozenset({"respectful"}),
        message="谢谢",
        recent_messages=[],
        today=date(2026, 8, 2),
        degraded=True,
    )

    assert decision.delta == 0
    assert decision.rule_id == "REL_FALLBACK"
