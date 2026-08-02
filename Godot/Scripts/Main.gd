extends Node2D


func _ready() -> void:
	if not ContentLoader.is_ready():
		push_error("Cyber Town content failed to load: %s" % ContentLoader.last_error)
		return
	print("Cyber Town content ready: %d NPCs, version %s" % [ContentLoader.get_enabled_profiles().size(), ContentLoader.content_version])
