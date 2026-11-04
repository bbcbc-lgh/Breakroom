extends Node2D

const NPC_SCENE := preload("res://Character/NPC.tscn")
const PLAYER_SCENE := preload("res://Character/Player.tscn")
const DIALOGUE_UI_SCENE := preload("res://Dialogue/DialogueUI.tscn")
const STARTUP_OVERLAY_SCENE := preload("res://World/StartupOverlay.tscn")
const INTERACTION_PROMPT_SCENE := preload("res://Character/InteractionPrompt.tscn")

var player: CharacterBody2D
var dialogue_ui: CanvasLayer
var active_npc: Node
var startup_overlay: CanvasLayer
var backend_launch_attempted := false
var health_retry_count := 0
var health_poll_timer: Timer
var startup_exhausted := false

const HEALTH_RETRY_LIMIT := 10


func _ready() -> void:
	if not ContentLoader.is_ready():
		push_error("Breakroom content failed to load: %s" % ContentLoader.last_error)
		return
	_build_world()
	_build_npcs()
	_build_player()
	_build_ui()
	APIClient.check_health()
	print("Breakroom playable slice ready: %d NPCs, version %s" % [ContentLoader.get_enabled_profiles().size(), ContentLoader.content_version])


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
	startup_overlay = STARTUP_OVERLAY_SCENE.instantiate()
	add_child(startup_overlay)
	startup_overlay.retry_requested.connect(_retry_backend_startup)
	APIClient.health_received.connect(_on_backend_health)
	health_poll_timer = Timer.new()
	health_poll_timer.wait_time = 15.0
	health_poll_timer.autostart = true
	health_poll_timer.timeout.connect(APIClient.check_health)
	add_child(health_poll_timer)
	if OS.get_environment("BREAKROOM_CAPTURE_KIND") != "":
		var capture_script = load("res://Tests/CaptureMainState.gd")
		var capture = capture_script.new()
		add_child(capture)


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


func _on_backend_health(available: bool, message: String, may_start_backend: bool) -> void:
	if available:
		health_retry_count = 0
		startup_exhausted = false
		startup_overlay.set_status(true, message)
		return
	if not may_start_backend:
		startup_overlay.set_status(false, message)
		return
	if startup_exhausted:
		startup_overlay.set_status(false, "本地服务启动超时。")
		return
	if backend_launch_attempted and not BackendProcessManager.owns_running_backend():
		backend_launch_attempted = false
	if not backend_launch_attempted:
		backend_launch_attempted = true
		if not BackendProcessManager.start_backend():
			startup_overlay.set_status(false, "找不到本地服务程序。")
			return
		startup_overlay.set_starting()
	if health_retry_count >= HEALTH_RETRY_LIMIT:
		BackendProcessManager.stop_owned_backend()
		startup_exhausted = true
		startup_overlay.set_status(false, "本地服务启动超时。")
		return
	health_retry_count += 1
	await get_tree().create_timer(0.5).timeout
	APIClient.check_health()


func _retry_backend_startup() -> void:
	BackendProcessManager.stop_owned_backend()
	backend_launch_attempted = false
	health_retry_count = 0
	startup_exhausted = false
	startup_overlay.set_starting()
	APIClient.check_health()
