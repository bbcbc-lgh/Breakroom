extends Node

var content_version: String = ""
var profiles: Array = []
var last_error: String = ""


func _ready() -> void:
	load_profiles()


func get_content_path() -> String:
	if OS.has_feature("editor"):
		return ProjectSettings.globalize_path("res://../Content/NPCProfiles.json")
	return OS.get_executable_path().get_base_dir().path_join("Content/NPCProfiles.json")


func load_profiles() -> bool:
	last_error = ""
	profiles.clear()
	var path := get_content_path()
	if not FileAccess.file_exists(path):
		return _fail("NPC config not found: %s" % path)

	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _fail("NPC config cannot be opened: %s" % path)

	var parser := JSON.new()
	var parse_result := parser.parse(file.get_as_text())
	if parse_result != OK:
		return _fail("NPC config JSON error at line %d: %s" % [parser.get_error_line(), parser.get_error_message()])

	var payload = parser.data
	if not payload is Dictionary:
		return _fail("NPC config root must be an object")
	if payload.get("schema_version") != 1:
		return _fail("NPC config schema_version must be 1")
	if not payload.get("content_version") is String or payload["content_version"].is_empty():
		return _fail("NPC config content_version must be a non-empty string")
	if not payload.get("npcs") is Array or payload["npcs"].is_empty():
		return _fail("NPC config npcs must be a non-empty array")

	var seen_ids := {}
	var required_fields := ["npc_id", "enabled", "name", "title", "appearance_key", "spawn", "wander"]
	for index in payload["npcs"].size():
		var profile = payload["npcs"][index]
		if not profile is Dictionary:
			return _fail("npcs[%d] must be an object" % index)
		for field in required_fields:
			if not profile.has(field):
				return _fail("npcs[%d].%s is required" % [index, field])
		var npc_id = profile["npc_id"]
		if not npc_id is String or npc_id.is_empty():
			return _fail("npcs[%d].npc_id must be a non-empty string" % index)
		if seen_ids.has(npc_id):
			return _fail("duplicate npc_id: %s" % npc_id)
		seen_ids[npc_id] = true

	content_version = payload["content_version"]
	profiles = payload["npcs"].duplicate(true)
	return true


func is_ready() -> bool:
	return last_error.is_empty() and not profiles.is_empty()


func get_enabled_profiles() -> Array:
	return profiles.filter(func(profile): return profile.get("enabled", false)).duplicate(true)


func _fail(message: String) -> bool:
	last_error = message
	push_error(message)
	return false
