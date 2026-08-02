extends Node2D

const NPC_SCENE := preload("res://Scenes/NPC.tscn")
const PLAYER_SCENE := preload("res://Scenes/Player.tscn")
const DIALOGUE_UI_SCENE := preload("res://Scenes/DialogueUI.tscn")
const STARTUP_OVERLAY_SCENE := preload("res://Scenes/StartupOverlay.tscn")
const INTERACTION_PROMPT_SCENE := preload("res://Scenes/InteractionPrompt.tscn")

var player: CharacterBody2D
var dialogue_ui: CanvasLayer
var active_npc: Node


func _ready() -> void:
	if not ContentLoader.is_ready():
		push_error("Cyber Town content failed to load: %s" % ContentLoader.last_error)
		return
	_build_world()
	_build_npcs()
	_build_player()
	_build_ui()
	APIClient.check_health()
	print("Cyber Town playable slice ready: %d NPCs, version %s" % [ContentLoader.get_enabled_profiles().size(), ContentLoader.content_version])


func _build_world() -> void:
	var background := Sprite2D.new()
	background.texture = load("res://Assets/Interior/OfficeBackground.svg")
	background.position = Vector2(640, 360)
	background.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	add_child(background)
	var obstacles := Node2D.new()
	obstacles.name = "WallsAndFurniture"
	add_child(obstacles)
	_add_block(obstacles, Vector2(640, 24), Vector2(1240, 32))
	_add_block(obstacles, Vector2(640, 696), Vector2(1240, 32))
	_add_block(obstacles, Vector2(24, 360), Vector2(32, 640))
	_add_block(obstacles, Vector2(1256, 360), Vector2(32, 640))
	_add_block(obstacles, Vector2(300, 236), Vector2(260, 34))
	_add_block(obstacles, Vector2(640, 236), Vector2(260, 34))
	_add_block(obstacles, Vector2(1000, 232), Vector2(230, 34))
	_add_block(obstacles, Vector2(298, 480), Vector2(240, 32))
	_add_block(obstacles, Vector2(645, 500), Vector2(290, 32))
	_add_block(obstacles, Vector2(1000, 480), Vector2(220, 32))


func _add_block(parent: Node, center: Vector2, size: Vector2) -> void:
	var body := StaticBody2D.new()
	body.collision_layer = 1
	body.collision_mask = 3
	body.position = center
	var shape_node := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = size
	shape_node.shape = shape
	body.add_child(shape_node)
	parent.add_child(body)


func _build_player() -> void:
	player = PLAYER_SCENE.instantiate()
	player.position = Vector2(640, 610)
	add_child(player)
	player.interaction_requested.connect(_on_interaction_requested)


func _build_npcs() -> void:
	var npcs := Node2D.new()
	npcs.name = "NPCs"
	add_child(npcs)
	for profile in ContentLoader.get_enabled_profiles():
		var npc := NPC_SCENE.instantiate()
		npc.setup(profile)
		npcs.add_child(npc)


func _build_ui() -> void:
	dialogue_ui = DIALOGUE_UI_SCENE.instantiate()
	add_child(dialogue_ui)
	dialogue_ui.configure(APIClient)
	dialogue_ui.closed.connect(_on_dialogue_closed)
	var prompt := INTERACTION_PROMPT_SCENE.instantiate()
	add_child(prompt)
	player.target_changed.connect(prompt.set_target)
	var overlay := STARTUP_OVERLAY_SCENE.instantiate()
	add_child(overlay)
	APIClient.health_received.connect(overlay.set_status)
	if OS.get_environment("CYBER_TOWN_CAPTURE_DIALOGUE_PATH") != "":
		var capture_script = load("res://Tests/CaptureDialogue.gd")
		var capture = capture_script.new()
		add_child(capture)
	if OS.get_environment("CYBER_TOWN_CAPTURE_PATH") != "":
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		var image := get_viewport().get_texture().get_image()
		var output := OS.get_environment("CYBER_TOWN_CAPTURE_PATH")
		var result := image.save_png(output)
		print("Captured %dx%d -> %s" % [image.get_width(), image.get_height(), output])
		get_tree().quit(0 if result == OK else 1)


func _on_interaction_requested(npc: Node) -> void:
	active_npc = npc
	player.set_interacting(true)
	npc.set_interacting(true)
	dialogue_ui.start_dialogue(npc)


func _on_dialogue_closed() -> void:
	player.set_interacting(false)
	if is_instance_valid(active_npc):
		active_npc.set_interacting(false)
	active_npc = null
