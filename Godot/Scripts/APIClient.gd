extends Node

signal health_received(available: bool, message: String, may_start_backend: bool)
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
		_emit_failure(kind, context_id, "无法连接本地服务。", true)


func _on_request_completed(
	result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray,
	request: HTTPRequest, kind: String, context_id: String,
) -> void:
	_remove_request(request)
	if result != HTTPRequest.RESULT_SUCCESS:
		_emit_failure(kind, context_id, "本地服务尚未启动。", true)
		return
	var text := body.get_string_from_utf8()
	var parsed = JSON.parse_string(text)
	if response_code < 200 or response_code >= 300 or not parsed is Dictionary:
		var detail := "后端暂时不可用。"
		if parsed is Dictionary and parsed.has("error"):
			detail = str(parsed["error"].get("message", detail))
		if kind == "health":
			detail = "端口 8765 被不兼容的服务占用。"
		_emit_failure(kind, context_id, detail, false)
		return
	match kind:
		"health": _emit_health(parsed)
		"dialogue": dialogue_received.emit(parsed)
		"conversation":
			parsed["requested_npc_id"] = context_id
			conversation_received.emit(parsed)


func _emit_health(payload: Dictionary) -> void:
	if str(payload.get("version", "")) != "0.1.0":
		health_received.emit(false, "本地服务版本不兼容。", false)
		return
	if str(payload.get("content_version", "")) != ContentLoader.content_version:
		health_received.emit(false, "NPC 配置版本不一致，请重启游戏与服务。", false)
		return
	if str(payload.get("status", "")) != "ready" or not bool(payload.get("database_ready", false)):
		health_received.emit(false, "本地数据库尚未就绪。", false)
		return
	var mode := str(payload.get("dialogue_mode", "mock"))
	health_received.emit(true, "AI 模式" if mode == "model" else "本地模式", false)


func _emit_failure(
	kind: String, context_id: String, message: String, may_start_backend := false
) -> void:
	if kind == "health":
		health_received.emit(false, message, may_start_backend)
	elif kind == "conversation":
		conversation_failed.emit(message, context_id)
	else:
		dialogue_failed.emit(message, context_id)


func _remove_request(request: HTTPRequest) -> void:
	_requests.erase(request)
	request.queue_free()
