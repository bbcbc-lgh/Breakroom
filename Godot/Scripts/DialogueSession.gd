class_name DialogueSession
extends RefCounted

enum State { CLOSED, LOADING, READY, WAITING, ERROR }

var state := State.CLOSED
var pending_request_id := ""
var rendered_request_ids: Dictionary = {}


func open() -> void:
	state = State.LOADING
	pending_request_id = ""


func ready() -> void:
	state = State.READY


func begin_send(request_id: String) -> bool:
	if state == State.WAITING or request_id.is_empty():
		return false
	pending_request_id = request_id
	state = State.WAITING
	return true


func fail() -> void:
	if not pending_request_id.is_empty():
		state = State.ERROR


func retry_request_id() -> String:
	return pending_request_id if state == State.ERROR else ""


func accept_response(request_id: String) -> bool:
	if request_id != pending_request_id:
		return false
	if rendered_request_ids.has(request_id):
		pending_request_id = ""
		state = State.READY
		return false
	rendered_request_ids[request_id] = true
	pending_request_id = ""
	state = State.READY
	return true


func close() -> void:
	state = State.CLOSED
	pending_request_id = ""
