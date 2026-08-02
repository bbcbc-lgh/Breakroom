from __future__ import annotations

import re
import unicodedata
from datetime import date

from CyberTown.Domain.Relationship import (
    RelationshipDecision,
    RelationshipState,
    relationship_level,
)

POSITIVE_RULES = {
    "helpful": (3, "REL_HELPFUL", "主动提供帮助"),
    "respectful": (2, "REL_RESPECTFUL", "礼貌交流"),
    "shares_personal_fact": (1, "REL_PERSONAL", "分享个人信息"),
    "curious": (1, "REL_CURIOUS", "认真交流"),
}


def normalize_message(message: str) -> str:
    normalized = unicodedata.normalize("NFKC", message).casefold()
    return re.sub(r"\s+", "", normalized)


class RelationshipService:
    def decide(
        self,
        *,
        state: RelationshipState,
        interaction_tags: frozenset[str],
        message: str,
        recent_messages: list[str],
        today: date,
        degraded: bool,
    ) -> RelationshipDecision:
        today_text = today.isoformat()
        positive_today = (
            state.positive_points_today if state.positive_points_date == today_text else 0
        )

        if degraded:
            delta, rule_id, reason = 0, "REL_FALLBACK", "本地降级回应"
        elif normalize_message(message) in {normalize_message(item) for item in recent_messages}:
            delta, rule_id, reason = 0, "REL_REPEAT", "重复内容不累计关系"
        elif "hostile" in interaction_tags:
            delta, rule_id, reason = -6, "REL_HOSTILE", "敌意表达"
        elif "rude" in interaction_tags:
            delta, rule_id, reason = -4, "REL_RUDE", "不友好表达"
        else:
            matches = [
                POSITIVE_RULES[tag] for tag in POSITIVE_RULES if tag in interaction_tags
            ]
            if matches:
                delta = min(4, sum(item[0] for item in matches))
                rule_id = "+".join(item[1] for item in matches)
                reason = matches[-1][2]
            else:
                delta, rule_id, reason = 0, "REL_NEUTRAL", "普通交流"

        if delta > 0:
            delta = min(delta, max(0, 12 - positive_today))
            if delta == 0:
                rule_id, reason = "REL_DAILY_CAP", "今日正向关系已达上限"

        old_score = state.score
        new_score = max(0, min(100, old_score + max(-6, min(4, delta))))
        actual_delta = new_score - old_score
        return RelationshipDecision(
            old_score=old_score,
            new_score=new_score,
            delta=actual_delta,
            level=relationship_level(new_score),
            rule_id=rule_id,
            reason=reason,
            interaction_count=state.interaction_count + 1,
            positive_points_today=positive_today + max(0, actual_delta),
            positive_points_date=today_text,
        )
