extends Node


func _ready() -> void:
	var main = get_tree().current_scene
	var capture_kind := OS.get_environment("BREAKROOM_CAPTURE_KIND")
	if capture_kind == "dialogue_mock":
		var npc = main.get_node("NPCs").get_child(0)
		main._on_interaction_requested(npc)
		main.dialogue_ui._on_conversation_received({
			"requested_npc_id": str(npc.profile.get("npc_id", "")),
			"relationship": {"level": "友好"},
			"messages": [
				{"role": "player", "content": "如何验证这次发布构建？"},
				{
					"role": "npc",
					"content": "先固定输入与环境，再逐项记录可复现的验收证据。",
				},
			],
		})
	elif capture_kind == "dialogue_error":
		var npc = main.get_node("NPCs").get_child(0)
		main._on_interaction_requested(npc)
		main.dialogue_ui._on_conversation_failed(
			"后端离线。", str(npc.profile.get("npc_id", ""))
		)
	elif capture_kind == "startup_error":
		main.startup_overlay.set_status(
			false, "端口 8765 已被不兼容服务占用，请关闭冲突程序后重试。"
		)
	elif capture_kind != "main":
		push_error("Unknown capture kind: %s" % capture_kind)
		get_tree().quit(1)
		return
	await get_tree().create_timer(0.1).timeout
	var output := OS.get_environment("BREAKROOM_CAPTURE_PATH")
	var image := get_viewport().get_texture().get_image()
	var result := image.save_png(output)
	print("Captured %s %dx%d -> %s" % [capture_kind, image.get_width(), image.get_height(), output])
	get_tree().quit(0 if result == OK else 1)
