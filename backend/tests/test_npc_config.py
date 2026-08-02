import json
from pathlib import Path

import pytest

from CyberTown.Config import PROJECT_ROOT
from CyberTown.Infrastructure.NPCConfigLoader import NPCConfigError, NPCConfigLoader


def test_loads_canonical_npc_profiles() -> None:
    document = NPCConfigLoader().load(PROJECT_ROOT / "Content" / "NPCProfiles.json")

    assert document.content_version == "1"
    assert [npc.npc_id for npc in document.npcs] == [
        "zhang_xu",
        "fan_yueyi",
        "hu_jialao",
    ]


def test_rejects_duplicate_npc_ids(tmp_path: Path) -> None:
    source = PROJECT_ROOT / "Content" / "NPCProfiles.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["npcs"][1]["npc_id"] = payload["npcs"][0]["npc_id"]
    invalid_path = tmp_path / "NPCProfiles.json"
    invalid_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(NPCConfigError, match="duplicate npc_id"):
        NPCConfigLoader().load(invalid_path)


def test_reports_nested_field_path(tmp_path: Path) -> None:
    source = PROJECT_ROOT / "Content" / "NPCProfiles.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["npcs"][1]["wander"]["radius"] = 999
    invalid_path = tmp_path / "NPCProfiles.json"
    invalid_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(NPCConfigError, match=r"npcs\[1\]\.wander\.radius"):
        NPCConfigLoader().load(invalid_path)


def test_rejects_unknown_appearance_key(tmp_path: Path) -> None:
    source = PROJECT_ROOT / "Content" / "NPCProfiles.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["npcs"][0]["appearance_key"] = "missing_style"
    invalid_path = tmp_path / "NPCProfiles.json"
    invalid_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(NPCConfigError, match="unknown appearance_key"):
        NPCConfigLoader().load(invalid_path)
