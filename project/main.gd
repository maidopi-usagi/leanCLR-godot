extends Node

func _ready() -> void:
	var script := ResourceLoader.load("res://hello.lcs")
	if script == null:
		push_error("Failed to load LeanCLR hello.lcs")
		get_tree().quit(1)
		return

	print("Loaded LeanCLR script: ", script.get_type_name())
	get_tree().quit()
