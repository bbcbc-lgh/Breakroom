extends CharacterBody2D

signal interaction_requested(npc: Node)
signal target_changed(npc: Node)

const SPEED := 190.0
var interacting := false
var nearby_npcs: Array[Node] = []
var facing := Vector2.UP
var character_sprite: Sprite2D
var facing_marker: Polygon2D


func _ready() -> void:
	add_to_group("player")
	collision_layer = 1
	collision_mask = 3
	character_sprite = Sprite2D.new()
	character_sprite.texture = load("res://Assets/Characters/player.svg")
	add_child(character_sprite)
	facing_marker = Polygon2D.new()
	facing_marker.polygon = PackedVector2Array([Vector2(0, -6), Vector2(-4, 3), Vector2(4, 3)])
	facing_marker.color = Color("#fff4a6")
	facing_marker.position = Vector2(0, 34)
	facing_marker.z_index = 2
	add_child(facing_marker)
	var collision := CollisionShape2D.new()
	var shape := CapsuleShape2D.new()
	shape.radius = 18.0
	shape.height = 50.0
	collision.shape = shape
	add_child(collision)


func _physics_process(_delta: float) -> void:
	if interacting:
		velocity = Vector2.ZERO
	else:
		var direction := Input.get_vector("move_left", "move_right", "move_up", "move_down")
		velocity = direction * SPEED
		if direction.length_squared() > 0.01:
			facing = direction
			character_sprite.flip_h = direction.x < -0.1
			facing_marker.rotation = direction.angle() + PI / 2.0
	move_and_slide()
	if Input.is_action_just_pressed("interact") and not interacting:
		var target := _nearest_npc()
		if target != null:
			interaction_requested.emit(target)
	target_changed.emit(null if interacting else _nearest_npc())


func set_interacting(value: bool) -> void:
	interacting = value


func register_npc(npc: Node, entered: bool) -> void:
	if entered:
		if not nearby_npcs.has(npc):
			nearby_npcs.append(npc)
	else:
		nearby_npcs.erase(npc)


func _nearest_npc() -> Node:
	return InteractionSelector.choose(global_position, facing, nearby_npcs)
