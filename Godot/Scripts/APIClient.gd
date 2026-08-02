extends Node

signal health_received(available: bool, message: String)
signal dialogue_received(payload: Dictionary)
signal dialogue_failed(message: String, client_request_id: String)
signal conversation_received(payload: Dictionary)
signal conversation_failed(message: String, npc_id: String)

const BASE_URL := "http://127.0.0.1:8765"
const PLAYER_ID := "local-player"

var _requests: Array[HTTPRequest] = []


func check_health() -> void:
	_request("/health", HTTPClient.METHOD_GET, {}, "health", "")


func send_dialogue(npc_id: String, message: String, client_request_id: String) -> void:
	_request(
		"/api/v1/dialogues",
		HTTPClient.METHOD_POST,
		{
			"client_request_id": client_request_id,
			"player_id": PLAYER_ID,
			"npc_id": npc_id,
			"message": message,
		},
		"dialogue",
		client_request_id,
	)


func load_conversation(npc_id: String) -> void:
	_request(
		"/api/v1/conversations/%s?player_id=%s&limit=20" % [npc_id, PLAYER_ID],
		HTTPClient.METHOD_GET,
		{},
		"conversation",
		npc_id,
	)


func _request(
	path: String, method: HTTPClient.Method, body: Dictionary, kind: String, context_id: String
) -> void:
	var request := HTTPRequest.new()
	request.timeout = 20.0 if kind != "health" else 2.0
	add_child(request)
	_requests.append(request)
	request.request_completed.connect(_on_request_completed.bind(request, kind, context_id))
	var headers := PackedStringArray(["Content-Type: application/json"])
	var payload := JSON.stringify(body) if not body.is_empty() else ""
	var error := request.request(BASE_URL + path, headers, method, payload)
	if error != OK:
		_remove_request(request)
		_emit_failure(kind, context_id, "无法连接后端，请确认 FastAPI 已启动。")


func _on_request_completed(
	result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray,
	request: HTTPRequest, kind: String, context_id: String,
) -> void:
	_remove_request(request)
	if result != HTTPRequest.RESULT_SUCCESS:
		_emit_failure(kind, context_id, "后端连接中断，请稍后重试。")
		return
	var text := body.get_string_from_utf8()
	var parsed = JSON.parse_string(text)
	if response_code < 200 or response_code >= 300 or not parsed is Dictionary:
		var detail := "后端暂时不可用。"
		if parsed is Dictionary and parsed.has("error"):
			detail = str(parsed["error"].get("message", detail))
		_emit_failure(kind, context_id, detail)
		return
	match kind:
		"health": health_received.emit(true, "本地模式")
		"dialogue": dialogue_received.emit(parsed)
		"conversation":
			parsed["requested_npc_id"] = context_id
			conversation_received.emit(parsed)


func _emit_failure(kind: String, context_id: String, message: String) -> void:
	if kind == "health":
		health_received.emit(false, message)
	elif kind == "conversation":
		conversation_failed.emit(message, context_id)
	else:
		dialogue_failed.emit(message, context_id)


func _remove_request(request: HTTPRequest) -> void:
	_requests.erase(request)
	request.queue_free()
