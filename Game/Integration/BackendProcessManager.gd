extends Node

var owned_pid := -1


func start_backend() -> bool:
	if owns_running_backend():
		return true
	var command := _backend_command()
	if command.is_empty():
		return false
	owned_pid = OS.create_process(command[0], command.slice(1), false)
	return owned_pid > 0


func owns_running_backend() -> bool:
	return owned_pid > 0 and OS.is_process_running(owned_pid)


func stop_owned_backend() -> void:
	if owns_running_backend():
		OS.kill(owned_pid)
	owned_pid = -1


func _exit_tree() -> void:
	stop_owned_backend()


func _backend_command() -> PackedStringArray:
	if OS.has_feature("editor"):
		var root := ProjectSettings.globalize_path("res://..").simplify_path()
		var python := root.path_join("Backend/.venv/Scripts/pythonw.exe")
		if not FileAccess.file_exists(python):
			python = root.path_join("Backend/.venv/Scripts/python.exe")
		var launcher := root.path_join("Backend/RunBackend.py")
		if not FileAccess.file_exists(python) or not FileAccess.file_exists(launcher):
			return PackedStringArray()
		return PackedStringArray([python, launcher])
	var executable_root := OS.get_executable_path().get_base_dir()
	var backend := executable_root.path_join("Backend/BreakroomBackend.exe")
	var content := executable_root.path_join("Content/NPCProfiles.json")
	if not FileAccess.file_exists(backend) or not FileAccess.file_exists(content):
		return PackedStringArray()
	return PackedStringArray([backend, "--content-path", content])
