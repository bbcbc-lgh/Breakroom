extends CanvasLayer

var target: Node
var panel: Panel
var label: Label


func _ready() -> void:
	panel = Panel.new()
	panel.size = Vector2(146, 38)
	var style := StyleBoxFlat.new()
	style.bg_color = Color("#1b2638e8")
	style.border_color = Color("#f4cc76")
	style.set_border_width_all(2)
	style.set_corner_radius_all(7)
	panel.add_theme_stylebox_override("panel", style)
	panel.visible = false
	add_child(panel)
	label = Label.new()
	label.set_anchors_preset(Control.PRESET_FULL_RECT)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_color_override("font_color", Color("#fff4a6"))
	panel.add_child(label)


func set_target(npc: Node) -> void:
	if target == npc:
		return
	if is_instance_valid(target):
		target.set_targeted(false)
	target = npc
	if is_instance_valid(target):
		target.set_targeted(true)
		label.text = "E  ·  %s" % str(target.profile.get("name", "NPC"))
		panel.visible = true
	else:
		panel.visible = false


func _process(_delta: float) -> void:
	if not is_instance_valid(target) or not panel.visible:
		return
	var player := get_tree().get_first_node_in_group("player") as Node2D
	if player == null:
		return
	var midpoint: Vector2 = (
		(player.global_position + target.global_position) * 0.5 + Vector2(0, -62)
	)
	var viewport_size := get_viewport().get_visible_rect().size
	panel.position = Vector2(
		clampf(midpoint.x - panel.size.x * 0.5, 12.0, viewport_size.x - panel.size.x - 12.0),
		clampf(midpoint.y, 12.0, viewport_size.y - panel.size.y - 12.0),
	)
