extends Node


func _ready() -> void:
	await get_tree().process_frame
	var main = get_tree().current_scene
	var npc = main.get_node("NPCs").get_child(0)
	main._on_interaction_requested(npc)
	main.dialogue_ui._on_conversation_failed("后端离线", str(npc.profile.get("npc_id", "")))
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var output := OS.get_environment("CYBER_TOWN_CAPTURE_DIALOGUE_PATH")
	var image := get_viewport().get_texture().get_image()
	var result := image.save_png(output)
	print("Captured dialogue %dx%d -> %s" % [image.get_width(), image.get_height(), output])
	get_tree().quit(0 if result == OK else 1)
