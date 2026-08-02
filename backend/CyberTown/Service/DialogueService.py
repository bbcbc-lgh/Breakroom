from __future__ import annotations

import asyncio
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import aiosqlite

from CyberTown.Agent.NPCContextBuilder import NPCContextBuilder
from CyberTown.Agent.NPCDialogueAgent import NPCDialogueAgent
from CyberTown.Domain.Dialogue import DialogueResult
from CyberTown.Domain.Relationship import relationship_level
from CyberTown.Repository.Database import Database
from CyberTown.Repository.DialogueRepository import DialogueRepository, StoredTurn
from CyberTown.Repository.RelationshipRepository import RelationshipRepository
from CyberTown.Service.MemoryService import MemoryService
from CyberTown.Service.NPCService import NPCService
from CyberTown.Service.RelationshipService import RelationshipService


class RequestIdConflictError(RuntimeError):
    pass


class PersistenceError(RuntimeError):
    pass


class DialogueService:
    def __init__(
        self,
        *,
        database: Database,
        npc_service: NPCService,
        context_builder: NPCContextBuilder,
        dialogue_agent: NPCDialogueAgent,
        dialogue_repository: DialogueRepository,
        relationship_repository: RelationshipRepository,
        memory_service: MemoryService,
        relationship_service: RelationshipService,
    ) -> None:
        self._database = database
        self._npc_service = npc_service
        self._context_builder = context_builder
        self._dialogue_agent = dialogue_agent
        self._dialogue_repository = dialogue_repository
        self._relationship_repository = relationship_repository
        self._memory_service = memory_service
        self._relationship_service = relationship_service
        self._locks: defaultdict[tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)

    async def create_dialogue(
        self,
        *,
        request_id: str,
        client_request_id: str,
        player_id: str,
        npc_id: str,
        message: str,
    ) -> DialogueResult:
        profile = self._npc_service.get_profile(npc_id)
        fingerprint = self._fingerprint(player_id, npc_id, message)
        lock = self._locks[(player_id, npc_id)]
        async with lock:
            try:
                async with self._database.connection() as connection:
                    existing = await self._dialogue_repository.find_by_client_request_id(
                        connection, client_request_id
                    )
                    if existing:
                        return self._existing_result(existing, fingerprint, profile)
                    relationship = await self._relationship_repository.get(
                        connection, player_id, npc_id
                    )
                    recent_messages = await self._dialogue_repository.list_recent_messages(
                        connection, player_id, npc_id
                    )
                    memory_matches = await self._memory_service.retrieve(
                        connection, player_id, npc_id, message
                    )

                context = self._context_builder.build(
                    profile=profile,
                    player_id=player_id,
                    player_message=message,
                    relationship_level=relationship_level(relationship.score),
                    recent_messages=recent_messages,
                    relevant_memories=tuple(match.summary for match in memory_matches),
                )
                model_result = await self._dialogue_agent.respond(context)
                now = datetime.now(UTC)
                since = (now - timedelta(minutes=10)).isoformat()
                turn_id = str(uuid4())

                try:
                    async with self._database.transaction() as connection:
                        existing = await self._dialogue_repository.find_by_client_request_id(
                            connection, client_request_id
                        )
                        if existing:
                            return self._existing_result(existing, fingerprint, profile)
                        await self._dialogue_repository.ensure_player(
                            connection, player_id, now.isoformat()
                        )
                        relationship = await self._relationship_repository.get(
                            connection, player_id, npc_id
                        )
                        recent_player_messages = (
                            await self._dialogue_repository.recent_player_messages(
                                connection, player_id, npc_id, since
                            )
                        )
                        decision = self._relationship_service.decide(
                            state=relationship,
                            interaction_tags=model_result.interaction_tags,
                            message=message,
                            recent_messages=recent_player_messages,
                            today=datetime.now().astimezone().date(),
                            degraded=model_result.degraded,
                        )
                        await self._dialogue_repository.insert_turn(
                            connection,
                            turn_id=turn_id,
                            request_id=request_id,
                            client_request_id=client_request_id,
                            request_fingerprint=fingerprint,
                            player_id=player_id,
                            npc_id=npc_id,
                            npc_name=profile.name,
                            npc_title=profile.title,
                            player_message=message,
                            model_result=model_result,
                            relationship=decision,
                            memory_saved=False,
                            created_at=now.isoformat(),
                        )
                        memory_saved = await self._memory_service.save_candidates(
                            connection,
                            source_turn_id=turn_id,
                            player_id=player_id,
                            npc_id=npc_id,
                            candidates=model_result.memory_candidates,
                            created_at=now.isoformat(),
                        )
                        await self._dialogue_repository.set_memory_saved(
                            connection, turn_id, memory_saved
                        )
                        await self._memory_service.mark_recalled(connection, memory_matches)
                        await self._relationship_repository.save(
                            connection, player_id, npc_id, decision, now.isoformat()
                        )
                        await self._relationship_repository.add_event(
                            connection,
                            event_id=str(uuid4()),
                            turn_id=turn_id,
                            player_id=player_id,
                            npc_id=npc_id,
                            decision=decision,
                            created_at=now.isoformat(),
                        )
                except (RequestIdConflictError, aiosqlite.Error):
                    raise
                except Exception as exc:
                    raise PersistenceError("dialogue persistence failed") from exc

                return DialogueResult(
                    request_id=request_id,
                    client_request_id=client_request_id,
                    profile=profile,
                    reply=model_result.reply,
                    reply_source=model_result.reply_source,
                    relationship=decision,
                    memory_saved=memory_saved,
                    degraded=model_result.degraded,
                    created_at=now,
                    interaction_tags=model_result.interaction_tags,
                    memory_candidates=model_result.memory_candidates,
                )
            except (RequestIdConflictError, aiosqlite.Error):
                raise
            except OSError as exc:
                raise PersistenceError("dialogue persistence failed") from exc

    async def conversation(self, player_id: str, npc_id: str, limit: int) -> tuple:
        profile = self._npc_service.get_profile(npc_id)
        async with self._database.connection() as connection:
            relationship = await self._relationship_repository.get(connection, player_id, npc_id)
            turns = await self._dialogue_repository.list_turns(
                connection, player_id, npc_id, limit
            )
        return profile, relationship, turns

    def _existing_result(
        self, stored: StoredTurn, fingerprint: str, profile
    ) -> DialogueResult:
        if stored.request_fingerprint != fingerprint:
            raise RequestIdConflictError(stored.client_request_id)
        return DialogueResult(
            request_id=stored.request_id,
            client_request_id=stored.client_request_id,
            profile=profile.model_copy(
                update={
                    "name": stored.npc_name,
                    "title": stored.npc_title or profile.title,
                }
            ),
            reply=stored.npc_reply,
            reply_source=stored.reply_source,
            relationship=stored.relationship,
            memory_saved=stored.memory_saved,
            degraded=stored.reply_source == "fallback",
            created_at=stored.created_at,
            interaction_tags=stored.interaction_tags,
            memory_candidates=(),
        )

    @staticmethod
    def _fingerprint(player_id: str, npc_id: str, message: str) -> str:
        payload = json.dumps(
            {"player_id": player_id, "npc_id": npc_id, "message": message},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
