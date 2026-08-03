extends CanvasLayer

signal closed

var panel: Panel
var npc_name_label: Label
var npc_title_label: Label
var relationship_label: Label
var history_label: RichTextLabel
var input: LineEdit
var send_button: Button
var close_button: Button
var status_label: Label
var active_npc: Node
var active_npc_id := ""
var pending_request_id := ""
var api_client: Node
var last_message := ""
var session := DialogueSession.new()
var waiting_timer: Timer
var waiting_frame := 0


func _ready() -> void:
	_build_ui()
	visible = false


func configure(client: Node) -> void:
	api_client = client
	api_client.dialogue_received.connect(_on_dialogue_received)
	api_client.dialogue_failed.connect(_on_dialogue_failed)
	api_client.conversation_received.connect(_on_conversation_received)
	api_client.conversation_failed.connect(_on_conversation_failed)


func start_dialogue(npc: Node) -> void:
	if waiting_timer != null:
		waiting_timer.stop()
	active_npc = npc
	active_npc_id = str(npc.profile.get("npc_id", ""))
	session.open()
	npc_name_label.text = str(npc.profile.get("name", "NPC"))
	npc_title_label.text = str(npc.profile.get("title", ""))
	relationship_label.text = "关系：陌生"
	status_label.text = "正在读取会话..."
	history_label.text = ""
	input.text = ""
	input.editable = true
	send_button.text = "发送"
	send_button.disabled = false
	visible = true
	input.grab_focus()
	api_client.load_conversation(active_npc_id)


func _build_ui() -> void:
	var margin := MarginContainer.new()
	margin.position = Vector2(28, 468)
	margin.size = Vector2(1224, 226)
	add_child(margin)
	panel = Panel.new()
	panel.add_theme_stylebox_override("panel", _panel_style(Color("#1b2638e8"), Color("#8ed5c6")))
	margin.add_child(panel)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 8)
	layout.set_anchors_preset(Control.PRESET_FULL_RECT)
	layout.offset_left = 22
	layout.offset_top = 18
	layout.offset_right = -22
	layout.offset_bottom = -18
	panel.add_child(layout)
	var header := HBoxContainer.new()
	layout.add_child(header)
	npc_name_label = Label.new()
	npc_name_label.add_theme_font_size_override("font_size", 24)
	header.add_child(npc_name_label)
	npc_title_label = Label.new()
	npc_title_label.add_theme_color_override("font_color", Color("#a6b6c9"))
	npc_title_label.add_theme_font_size_override("font_size", 16)
	header.add_child(npc_title_label)
	relationship_label = Label.new()
	relationship_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	relationship_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	relationship_label.add_theme_color_override("font_color", Color("#f4cc76"))
	header.add_child(relationship_label)
	history_label = RichTextLabel.new()
	history_label.bbcode_enabled = true
	history_label.fit_content = false
	history_label.scroll_active = true
	history_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(history_label)
	status_label = Label.new()
	status_label.add_theme_color_override("font_color", Color("#f4cc76"))
	layout.add_child(status_label)
	var row := HBoxContainer.new()
	layout.add_child(row)
	input = LineEdit.new()
	input.name = "PlayerInput"
	input.placeholder_text = "输入消息..."
	input.max_length = 300
	input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	input.text_submitted.connect(_on_text_submitted)
	row.add_child(input)
	send_button = Button.new()
	send_button.name = "SendButton"
	send_button.text = "发送"
	send_button.pressed.connect(_send)
	row.add_child(send_button)
	close_button = Button.new()
	close_button.name = "CloseButton"
	close_button.text = "关闭"
	close_button.pressed.connect(close_dialogue)
	row.add_child(close_button)
	input.focus_next = input.get_path_to(send_button)
	input.focus_previous = input.get_path_to(close_button)
	send_button.focus_next = send_button.get_path_to(close_button)
	send_button.focus_previous = send_button.get_path_to(input)
	close_button.focus_next = close_button.get_path_to(input)
	close_button.focus_previous = close_button.get_path_to(send_button)
	waiting_timer = Timer.new()
	waiting_timer.wait_time = 0.35
	waiting_timer.timeout.connect(_animate_waiting)
	add_child(waiting_timer)


func close_dialogue() -> void:
	if waiting_timer != null:
		waiting_timer.stop()
	session.close()
	visible = false
	active_npc = null
	closed.emit()


func _unhandled_input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("close_dialogue"):
		close_dialogue()
		get_viewport().set_input_as_handled()


func _send() -> void:
	var message := input.text.strip_edges()
	if message.is_empty() or session.state == DialogueSession.State.WAITING:
		return
	if session.state == DialogueSession.State.ERROR:
		pending_request_id = session.retry_request_id()
		message = last_message
	else:
		pending_request_id = _new_request_id()
		last_message = message
	if not session.begin_send(pending_request_id):
		return
	status_label.text = "正在思考..."
	waiting_frame = 0
	waiting_timer.start()
	send_button.text = "等待"
	send_button.disabled = true
	input.editable = false
	api_client.send_dialogue(active_npc_id, message, pending_request_id)


func _on_text_submitted(_text: String) -> void:
	_send()


func _on_conversation_received(payload: Dictionary) -> void:
	if not visible or str(payload.get("requested_npc_id", "")) != active_npc_id:
		return
	var relationship: Dictionary = payload.get("relationship", {})
	relationship_label.text = "关系：%s" % str(relationship.get("level", "陌生"))
	var lines: Array[String] = []
	for message in payload.get("messages", []):
		var role := "我" if message.get("role") == "player" else npc_name_label.text
		lines.append("[color=#a6b6c9]%s[/color]  %s" % [role, str(message.get("content", ""))])
	history_label.text = "\n".join(lines)
	status_label.text = "可以继续交流。"
	session.ready()


func _on_dialogue_received(payload: Dictionary) -> void:
	if not visible or str(payload.get("npc", {}).get("npc_id", "")) != active_npc_id:
		return
	var response_id := str(payload.get("client_request_id", ""))
	var should_render := session.accept_response(response_id)
	if not should_render:
		return
	pending_request_id = ""
	waiting_timer.stop()
	send_button.disabled = false
	input.editable = true
	send_button.text = "发送"
	var degraded := bool(payload.get("degraded", false))
	input.text = last_message if degraded else ""
	var relation: Dictionary = payload.get("relationship", {})
	relationship_label.text = "关系：%s  (%+d)" % [str(relation.get("level", "陌生")), int(relation.get("delta", 0))]
	var current := history_label.text
	if not current.is_empty():
		current += "\n"
	history_label.text = current + "[color=#a6b6c9]我[/color]  %s\n[color=#a6b6c9]%s[/color]  %s" % [last_message, npc_name_label.text, str(payload.get("reply", ""))]
	if degraded:
		status_label.text = "模型暂时不可用，已使用降级回复。可再次发送重试。"
		send_button.text = "再次尝试"
	else:
		status_label.text = "已保存。" if payload.get("memory_saved", false) else "已收到回复。"


func _on_dialogue_failed(message: String, request_id: String) -> void:
	if not visible or request_id != session.pending_request_id:
		return
	session.fail()
	waiting_timer.stop()
	send_button.disabled = false
	input.editable = true
	send_button.text = "重试"
	status_label.text = "%s 可点击重试。" % message


func _on_conversation_failed(message: String, npc_id: String) -> void:
	if not visible or npc_id != active_npc_id:
		return
	session.ready()
	status_label.text = "%s 仍可发送新消息。" % message


func _animate_waiting() -> void:
	waiting_frame = (waiting_frame + 1) % 4
	status_label.text = "正在思考%s" % ".".repeat(waiting_frame)


func _panel_style(fill: Color, border: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = border
	style.set_border_width_all(2)
	style.corner_radius_top_right = 6
	style.corner_radius_bottom_left = 6
	style.corner_radius_bottom_right = 6
	style.corner_radius_top_left = 6
	return style


func _new_request_id() -> String:
	var bytes := Crypto.new().generate_random_bytes(16)
	bytes[6] = (bytes[6] & 0x0f) | 0x40
	bytes[8] = (bytes[8] & 0x3f) | 0x80
	var encoded := bytes.hex_encode()
	return "%s-%s-%s-%s-%s" % [
		encoded.substr(0, 8), encoded.substr(8, 4), encoded.substr(12, 4),
		encoded.substr(16, 4), encoded.substr(20, 12),
	]
