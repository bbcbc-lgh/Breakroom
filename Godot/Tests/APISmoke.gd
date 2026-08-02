extends Node

var completed := false


func _ready() -> void:
	APIClient.dialogue_received.connect(_on_dialogue_received)
	APIClient.dialogue_failed.connect(_on_dialogue_failed)
	APIClient.send_dialogue(
		"zhang_xu",
		"谢谢，请帮我梳理测试边界",
		"6f1dd603-0db3-42e5-98ef-b93b198f4720",
	)
	get_tree().create_timer(5.0).timeout.connect(_on_timeout)


func _on_dialogue_received(payload: Dictionary) -> void:
	completed = true
	if payload.get("npc", {}).get("npc_id") != "zhang_xu":
		push_error("API smoke returned the wrong NPC")
		get_tree().quit(1)
		return
	if str(payload.get("reply", "")).is_empty():
		push_error("API smoke returned an empty reply")
		get_tree().quit(1)
		return
	print("Godot API smoke passed: %s" % payload.get("reply_source", ""))
	get_tree().quit(0)


func _on_dialogue_failed(message: String, _request_id: String) -> void:
	completed = true
	push_error("Godot API smoke failed: %s" % message)
	get_tree().quit(1)


func _on_timeout() -> void:
	if not completed:
		push_error("Godot API smoke timed out")
		get_tree().quit(1)
