extends CanvasLayer

signal retry_requested

var label: Label
var retry_button: Button
var exit_button: Button


func _ready() -> void:
	var row := HBoxContainer.new()
	row.position = Vector2(28, 18)
	row.size = Vector2(1224, 52)
	row.add_theme_constant_override("separation", 10)
	add_child(row)
	label = Label.new()
	label.text = "赛博小镇"
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 18)
	label.add_theme_color_override("font_color", Color("#f4cc76"))
	row.add_child(label)
	retry_button = Button.new()
	retry_button.text = "重试"
	retry_button.custom_minimum_size = Vector2(76, 38)
	retry_button.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	retry_button.visible = false
	retry_button.pressed.connect(retry_requested.emit)
	row.add_child(retry_button)
	exit_button = Button.new()
	exit_button.text = "退出"
	exit_button.custom_minimum_size = Vector2(76, 38)
	exit_button.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	exit_button.visible = false
	exit_button.pressed.connect(get_tree().quit)
	row.add_child(exit_button)


func set_starting() -> void:
	label.text = "赛博小镇  /  正在启动本地服务"
	label.add_theme_color_override("font_color", Color("#f4cc76"))
	retry_button.visible = false
	exit_button.visible = false


func set_status(available: bool, message: String) -> void:
	label.text = "赛博小镇  /  %s" % message
	label.add_theme_color_override(
		"font_color", Color("#8ed5c6") if available else Color("#e6a4a0")
	)
	retry_button.visible = not available
	exit_button.visible = not available
