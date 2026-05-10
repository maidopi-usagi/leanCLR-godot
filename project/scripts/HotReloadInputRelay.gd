extends Node

@onready var hot_reload_host: Node = get_node("../LiveHotReloadHost")

func _ready() -> void:
	set_process_input(true)

func _input(event: InputEvent) -> void:
	if hot_reload_host != null:
		hot_reload_host.forward_input(event)
