class_name InteractionSelector
extends RefCounted


static func choose(player_position: Vector2, facing: Vector2, candidates: Array) -> Node:
	var best: Node = null
	var best_distance := INF
	var best_alignment := -INF
	var normalized_facing := facing.normalized() if facing.length_squared() > 0.01 else Vector2.DOWN
	for candidate in candidates:
		if not is_instance_valid(candidate):
			continue
		var offset: Vector2 = candidate.global_position - player_position
		var distance := offset.length()
		var alignment := normalized_facing.dot(offset / distance) if distance > 0.01 else 1.0
		if distance < best_distance - 1.0 or (
			absf(distance - best_distance) <= 1.0 and alignment > best_alignment
		):
			best = candidate
			best_distance = distance
			best_alignment = alignment
	return best
