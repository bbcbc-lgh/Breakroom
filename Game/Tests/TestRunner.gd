extends SceneTree

const INTERACTION_SELECTOR = preload("res://Character/InteractionSelector.gd")
const DIALOGUE_SESSION = preload("res://Dialogue/DialogueSession.gd")
const DIALOGUE_UI_SCENE = preload("res://Dialogue/DialogueUI.tscn")
const STARTUP_OVERLAY_SCENE = preload("res://World/StartupOverlay.tscn")
const PLAYER_SCENE = preload("res://Character/Player.tscn")


class FakeAPIClient:
	extends Node
	signal dialogue_received(payload: Dictionary)
	signal dialogue_failed(message: String, client_request_id: String)
	signal conversation_received(payload: Dictionary)
	signal conversation_failed(message: String, npc_id: String)
	var sent_requests: Array[Dictionary] = []

	func load_conversation(npc_id: String) -> void:
		conversation_received.emit({
			"requested_npc_id": npc_id,
			"relationship": {"level": "陌生"},
			"messages": [],
		})

	func send_dialogue(npc_id: String, message: String, request_id: String) -> void:
		sent_requests.append({"npc_id": npc_id, "message": message, "request_id": request_id})


class FakeNPC:
	extends Node2D
	var profile: Dictionary

	func _init(npc_id: String, display_name: String) -> void:
		profile = {"npc_id": npc_id, "name": display_name, "title": "测试角色"}

var failures: Array[String] = []


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_content_loader()
	_test_interaction_selector()
	_test_dialogue_session()
	_test_health_contract()
	_test_backend_command()
	await _test_startup_overlay_layout()
	await _test_movement_collision_and_dialogue_lock()
	await _test_keyboard_dialogue_flow()
	await _test_keyboard_interaction()
	await process_frame
	if failures.is_empty():
		print("Godot tests passed: content, movement, collision, interaction, dialogue, health, runtime command, startup layout")
		quit(0)
	else:
		for failure in failures:
			push_error(failure)
		quit(1)


func _test_content_loader() -> void:
	var loader_script = load("res://Integration/ContentLoader.gd")
	var loader = loader_script.new()
	if not loader.load_profiles():
		failures.append("content loader could not read NPC profiles")
		return
	if loader.get_enabled_profiles().size() != 3:
		failures.append("expected three enabled NPC profiles")
	loader.free()


func _test_interaction_selector() -> void:
	var ahead := Node2D.new()
	ahead.position = Vector2(0, -45)
	var behind := Node2D.new()
	behind.position = Vector2(0, 55)
	root.add_child(ahead)
	root.add_child(behind)
	var selected = INTERACTION_SELECTOR.choose(Vector2.ZERO, Vector2.UP, [ahead, behind])
	if selected != ahead:
		failures.append("distance priority did not select the nearest NPC")
	behind.position = Vector2(0, 45)
	var side := Node2D.new()
	side.position = Vector2(45, 0)
	root.add_child(side)
	selected = INTERACTION_SELECTOR.choose(Vector2.ZERO, Vector2.RIGHT, [side, behind])
	if selected != side:
		failures.append("facing priority did not break an equal-distance tie")
	ahead.free()
	behind.free()
	side.free()


func _test_dialogue_session() -> void:
	var session = DIALOGUE_SESSION.new()
	session.open()
	session.ready()
	if not session.begin_send("request-1"):
		failures.append("ready session refused a request")
	if session.begin_send("request-2"):
		failures.append("waiting session allowed duplicate submit")
	session.fail()
	if session.retry_request_id() != "request-1":
		failures.append("retry did not preserve request id")
	if not session.begin_send(session.retry_request_id()):
		failures.append("retry request was rejected")
	if not session.accept_response("request-1"):
		failures.append("first response was not accepted")
	if session.accept_response("request-1"):
		failures.append("duplicate response was rendered")
	session.open()
	if session.accept_response("late-request"):
		failures.append("late response was rendered in another dialogue")
	session.ready()
	if not session.begin_send("stale-request"):
		failures.append("stale request setup failed")
	session.close()
	session.open()
	session.ready()
	if not session.begin_send("current-request"):
		failures.append("current request setup failed")
	if session.accept_response("stale-request"):
		failures.append("closed dialogue response was accepted after switching")
	if session.pending_request_id != "current-request":
		failures.append("late response cleared the current pending request")


func _test_health_contract() -> void:
	var api_client = root.get_node_or_null("APIClient")
	var content_loader = root.get_node_or_null("ContentLoader")
	if api_client == null or content_loader == null:
		failures.append("health contract autoloads are missing")
		return
	var content_version: String = content_loader.content_version
	var results: Array = []
	var callback := func(available: bool, message: String, may_start: bool):
		results.append([available, message, may_start])
	api_client.health_received.connect(callback)
	api_client._emit_health({
		"version": "0.1.0",
		"content_version": content_version,
		"status": "ready",
		"database_ready": true,
		"dialogue_mode": "mock",
	})
	api_client._emit_health({
		"version": "9.9.9",
		"content_version": content_version,
		"status": "ready",
		"database_ready": true,
		"dialogue_mode": "mock",
	})
	api_client._emit_health({
		"version": "0.1.0",
		"content_version": content_version,
		"status": "starting",
		"database_ready": false,
		"dialogue_mode": "mock",
	})
	api_client.health_received.disconnect(callback)
	if results.size() != 3 or results[0] != [true, "本地模式", false]:
		failures.append("compatible health response was rejected")
	if results[1][0] or results[1][2]:
		failures.append("incompatible backend was treated as startable")
	if results[2][0]:
		failures.append("unready database was treated as healthy")


func _test_backend_command() -> void:
	var manager = root.get_node_or_null("BackendProcessManager")
	if manager == null:
		failures.append("BackendProcessManager autoload is missing")
		return
	var command: PackedStringArray = manager._backend_command()
	if command.size() < 2:
		failures.append("development backend command could not be resolved")
		return
	if not FileAccess.file_exists(command[0]) or not FileAccess.file_exists(command[1]):
		failures.append("development backend command points to missing files")


func _test_startup_overlay_layout() -> void:
	var overlay = STARTUP_OVERLAY_SCENE.instantiate()
	root.add_child(overlay)
	await process_frame
	overlay.set_status(false, "端口 8765 已被不兼容服务占用，请关闭冲突程序后重试。")
	await process_frame
	var label_rect: Rect2 = overlay.label.get_global_rect()
	var retry_rect: Rect2 = overlay.retry_button.get_global_rect()
	var exit_rect: Rect2 = overlay.exit_button.get_global_rect()
	if not overlay.retry_button.visible or not overlay.exit_button.visible:
		failures.append("startup error did not expose retry and exit actions")
	if label_rect.end.x > retry_rect.position.x:
		failures.append("startup status overlaps the retry action")
	if exit_rect.end.x > root.get_viewport().get_visible_rect().end.x:
		failures.append("startup exit action exceeds the viewport")
	overlay.queue_free()
	await process_frame


func _test_movement_collision_and_dialogue_lock() -> void:
	var wall := StaticBody2D.new()
	wall.position = Vector2(280, 200)
	var wall_collision := CollisionShape2D.new()
	var wall_shape := RectangleShape2D.new()
	wall_shape.size = Vector2(40, 120)
	wall_collision.shape = wall_shape
	wall.add_child(wall_collision)
	root.add_child(wall)
	var player = PLAYER_SCENE.instantiate()
	player.position = Vector2(200, 200)
	root.add_child(player)
	await process_frame

	Input.action_press("move_right")
	for _index in 30:
		await physics_frame
	Input.action_release("move_right")
	if player.position.x <= 200.0:
		failures.append("movement input did not move the player")
	if player.position.x > 244.0:
		failures.append("player crossed a static collision body")

	player.set_interacting(true)
	var locked_position: Vector2 = player.position
	Input.action_press("move_left")
	for _index in 3:
		await physics_frame
	Input.action_release("move_left")
	if not player.position.is_equal_approx(locked_position):
		failures.append("dialogue state did not lock player movement")

	player.queue_free()
	wall.queue_free()
	await process_frame


func _test_keyboard_dialogue_flow() -> void:
	var client := FakeAPIClient.new()
	root.add_child(client)
	var ui = DIALOGUE_UI_SCENE.instantiate()
	root.add_child(ui)
	ui.configure(client)
	var first_npc := FakeNPC.new("zhang_xu", "张旭")
	var second_npc := FakeNPC.new("fan_yueyi", "樊玥燚")
	root.add_child(first_npc)
	root.add_child(second_npc)
	await process_frame

	ui.start_dialogue(first_npc)
	ui.input.text = "原始消息"
	ui._on_text_submitted(ui.input.text)
	if client.sent_requests.size() != 1 or ui.input.editable:
		failures.append("keyboard submit did not enter waiting state")
	var first_request: Dictionary = client.sent_requests[0]
	client.dialogue_failed.emit("暂时离线", first_request["request_id"])
	ui.input.text = "被修改的消息"
	ui._on_text_submitted(ui.input.text)
	if client.sent_requests.size() != 2:
		failures.append("keyboard retry did not send")
	else:
		var retry: Dictionary = client.sent_requests[1]
		if retry["request_id"] != first_request["request_id"] or retry["message"] != "原始消息":
			failures.append("transport retry changed the idempotent request payload")

	client.dialogue_received.emit({
		"client_request_id": first_request["request_id"],
		"npc": {"npc_id": "zhang_xu"},
		"reply": "降级回复",
		"degraded": true,
		"relationship": {"level": "陌生", "delta": 0},
	})
	ui._on_text_submitted(ui.input.text)
	if client.sent_requests.size() != 3:
		failures.append("degraded response could not be retried")
	else:
		var model_retry: Dictionary = client.sent_requests[2]
		if model_retry["request_id"] == first_request["request_id"]:
			failures.append("model retry reused a persisted fallback request id")

	var current_request: Dictionary = client.sent_requests[-1]
	ui.start_dialogue(second_npc)
	client.dialogue_received.emit({
		"client_request_id": current_request["request_id"],
		"npc": {"npc_id": "zhang_xu"},
		"reply": "迟到回复",
		"degraded": false,
		"relationship": {"level": "陌生", "delta": 0},
	})
	if ui.active_npc_id != "fan_yueyi" or not ui.input.editable:
		failures.append("late response corrupted the newly opened NPC dialogue")

	var escape := InputEventAction.new()
	escape.action = "close_dialogue"
	escape.pressed = true
	ui._unhandled_input(escape)
	if ui.visible:
		failures.append("Escape did not close the dialogue")
	ui.queue_free()
	client.queue_free()
	first_npc.queue_free()
	second_npc.queue_free()
	await process_frame


func _test_keyboard_interaction() -> void:
	var player = PLAYER_SCENE.instantiate()
	root.add_child(player)
	var npc := FakeNPC.new("zhang_xu", "张旭")
	npc.position = player.position + Vector2(0, -40)
	root.add_child(npc)
	await process_frame
	player.set_physics_process(false)
	player.register_npc(npc, true)
	var requested: Array = []
	player.interaction_requested.connect(func(target: Node): requested.append(target))
	Input.action_press("interact")
	player._physics_process(0.0)
	Input.action_release("interact")
	if requested != [npc]:
		failures.append("E key did not request interaction with the nearby NPC")
	player.queue_free()
	npc.queue_free()
	await process_frame
