extends SceneTree

const INTERACTION_SELECTOR = preload("res://Scripts/InteractionSelector.gd")
const DIALOGUE_SESSION = preload("res://Scripts/DialogueSession.gd")

var failures: Array[String] = []


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_content_loader()
	_test_interaction_selector()
	_test_dialogue_session()
	await process_frame
	if failures.is_empty():
		print("Godot tests passed: content, interaction selector, dialogue session")
		quit(0)
	else:
		for failure in failures:
			push_error(failure)
		quit(1)


func _test_content_loader() -> void:
	var loader_script = load("res://Autoload/ContentLoader.gd")
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
