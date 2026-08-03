extends CharacterBody2D

var profile: Dictionary = {}
var home_position := Vector2.ZERO
var wander_time := 0.0
var direction := Vector2.ZERO
var player: Node
var name_label: Label
var bubble: Label
var interacting := false
var visual_sprite: Sprite2D
var target_ring: Line2D
var pause_remaining := 0.0
var ambient_remaining := 8.0


func setup(npc_profile: Dictionary) -> void:
	profile = npc_profile
	name = str(profile.get("npc_id", "NPC"))
	global_position = Vector2(
		float(profile.get("spawn", {}).get("x", 640)),
		float(profile.get("spawn", {}).get("y", 360)),
	)
	home_position = global_position


func _ready() -> void:
	collision_layer = 2
	collision_mask = 1
	visual_sprite = Sprite2D.new()
	var appearance := str(profile.get("appearance_key", "engineer_teal"))
	var texture_path: String = {
		"engineer_teal": "res://Assets/Characters/engineer_teal.svg",
		"planner_amber": "res://Assets/Characters/planner_amber.svg",
		"designer_coral": "res://Assets/Characters/designer_coral.svg",
	}.get(appearance, "res://Assets/Characters/engineer_teal.svg")
	visual_sprite.texture = load(texture_path)
	add_child(visual_sprite)
	target_ring = Line2D.new()
	target_ring.width = 2.0
	target_ring.default_color = Color("#f4cc76")
	var points := PackedVector2Array()
	for index in 24:
		var angle := TAU * float(index) / 23.0
		points.append(Vector2(cos(angle) * 32.0, sin(angle) * 18.0 + 28.0))
	target_ring.points = points
	target_ring.visible = false
	add_child(target_ring)
	var collision := CollisionShape2D.new()
	var collision_shape := CapsuleShape2D.new()
	collision_shape.radius = 18.0
	collision_shape.height = 50.0
	collision.shape = collision_shape
	add_child(collision)
	player = get_tree().get_first_node_in_group("player")
	name_label = Label.new()
	name_label.text = str(profile.get("name", "NPC"))
	name_label.position = Vector2(-70, -76)
	name_label.size = Vector2(140, 24)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_label.add_theme_color_override("font_color", Color("#fff4a6"))
	name_label.add_theme_color_override("font_shadow_color", Color("#172033"))
	name_label.add_theme_constant_override("shadow_offset_x", 2)
	name_label.add_theme_constant_override("shadow_offset_y", 2)
	name_label.visible = false
	add_child(name_label)
	bubble = Label.new()
	bubble.visible = false
	bubble.position = Vector2(-92, -116)
	bubble.size = Vector2(184, 42)
	bubble.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	bubble.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	bubble.add_theme_color_override("font_color", Color("#172033"))
	add_child(bubble)
	var interaction_area := Area2D.new()
	interaction_area.collision_layer = 0
	interaction_area.collision_mask = 1
	interaction_area.monitoring = true
	var interaction_shape := CollisionShape2D.new()
	var shape := CircleShape2D.new()
	shape.radius = 72.0
	interaction_shape.shape = shape
	interaction_area.add_child(interaction_shape)
	interaction_area.body_entered.connect(_on_body_entered)
	interaction_area.body_exited.connect(_on_body_exited)
	add_child(interaction_area)


func _physics_process(delta: float) -> void:
	if interacting:
		velocity = Vector2.ZERO
		return
	var wander: Dictionary = profile.get("wander", {})
	if not bool(wander.get("enabled", true)):
		return
	ambient_remaining -= delta
	if ambient_remaining <= 0.0:
		ambient_remaining = randf_range(10.0, 18.0)
		say_ambient()
	if pause_remaining > 0.0:
		pause_remaining -= delta
		velocity = Vector2.ZERO
		return
	wander_time += delta
	if wander_time > 3.5:
		wander_time = 0.0
		var pause: Dictionary = wander.get("pause_seconds", {})
		pause_remaining = randf_range(
			float(pause.get("min", 3.0)), float(pause.get("max", 7.0))
		)
		var angle := (global_position.x * 0.013 + global_position.y * 0.017) + Time.get_ticks_msec() * 0.0001
		direction = Vector2(cos(angle), sin(angle))
	var radius := float(wander.get("radius", 64))
	if global_position.distance_to(home_position) > radius:
		direction = home_position - global_position
		if direction.length_squared() > 0.01:
			direction = direction.normalized()
	velocity = direction * float(wander.get("speed", 40))
	if absf(direction.x) > 0.1:
		visual_sprite.flip_h = direction.x < 0.0
	move_and_slide()


func set_interacting(value: bool) -> void:
	interacting = value


func set_targeted(value: bool) -> void:
	name_label.visible = value
	target_ring.visible = value


func say_ambient() -> void:
	var lines: Array = profile.get("ambient_lines", [])
	if lines.is_empty() or bubble == null:
		return
	bubble.text = str(lines[randi() % lines.size()])
	bubble.visible = true
	await get_tree().create_timer(4.0).timeout
	if is_instance_valid(bubble):
		bubble.visible = false


func _on_body_entered(body: Node) -> void:
	if body.is_in_group("player"):
		player = body
		body.register_npc(self, true)


func _on_body_exited(body: Node) -> void:
	if body.is_in_group("player"):
		body.register_npc(self, false)
