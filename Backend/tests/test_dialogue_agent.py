from src.Agent.BaseDialogueModelClient import BaseDialogueModelClient
from src.Agent.NPCDialogueAgent import NPCDialogueAgent
from src.Config import PROJECT_ROOT
from src.Domain.Dialogue import DialogueContext, DialogueModelResult
from src.Infrastructure.NPCConfigLoader import NPCConfigLoader


class UntrustedModelClient(BaseDialogueModelClient):
    async def generate(self, _context: DialogueContext) -> DialogueModelResult:
        return DialogueModelResult(
            reply="答" * 400,
            interaction_tags=frozenset({"respectful", "write_database"}),
        )


async def test_agent_limits_reply_and_filters_tags() -> None:
    profile = NPCConfigLoader().load(PROJECT_ROOT / "Content" / "NPCProfiles.json").npcs[0]
    context = DialogueContext(
        profile=profile,
        player_id="local-player",
        player_message="你好",
        relationship_level="陌生",
    )

    result = await NPCDialogueAgent(UntrustedModelClient()).respond(context)

    assert len(result.reply) == 280
    assert result.reply.endswith("…")
    assert result.interaction_tags == frozenset({"respectful"})
