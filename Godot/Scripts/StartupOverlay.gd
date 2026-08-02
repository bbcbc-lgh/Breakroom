extends CanvasLayer

var label: Label
var retry_button: Button
var exit_button: Button


func _ready() -> void:
	label = Label.new()
	label.position = Vector2(28, 24)
	label.size = Vector2(560, 52)
	label.text = "赛博小镇"
	label.add_theme_font_size_override("font_size", 18)
	label.add_theme_color_override("font_color", Color("#f4cc76"))
	add_child(label)
	retry_button = Button.new()
	retry_button.text = "重试"
	retry_button.position = Vector2(300, 18)
	retry_button.size = Vector2(76, 38)
	retry_button.visible = false
	retry_button.pressed.connect(APIClient.check_health)
	add_child(retry_button)
	exit_button = Button.new()
	exit_button.text = "退出"
	exit_button.position = Vector2(386, 18)
	exit_button.size = Vector2(76, 38)
	exit_button.visible = false
	exit_button.pressed.connect(get_tree().quit)
	add_child(exit_button)


func set_status(available: bool, _message: String) -> void:
	label.text = "赛博小镇  /  %s" % ("本地模式" if available else "本地服务未启动")
	label.add_theme_color_override(
		"font_color", Color("#8ed5c6") if available else Color("#e6a4a0")
	)
	retry_button.visible = not available
	exit_button.visible = not available
