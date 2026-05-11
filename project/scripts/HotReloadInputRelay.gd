extends Node

@export var marker_path := "res://leanclr/live_reload.txt"
@export var attached_assembly_name := ""
@export var reload_type_name := ""
@export var script_owner_path: NodePath
@export var reload_poll_seconds := 0.25

@onready var hot_reload_host: Node = get_node("../LiveHotReloadHost")

var _elapsed := 0.0

func _ready() -> void:
	if hot_reload_host != null:
		hot_reload_host.set_script_owner_path(script_owner_path)
		reload_from_marker()
	set_process(reload_poll_seconds > 0.0)
	set_process_input(true)

func _process(delta: float) -> void:
	_elapsed += delta
	if _elapsed >= reload_poll_seconds:
		_elapsed = 0.0
		reload_from_marker()

func _input(event: InputEvent) -> void:
	if hot_reload_host != null:
		hot_reload_host.forward_input(event)

func reload_from_marker() -> void:
	if hot_reload_host == null:
		return

	var assembly_name := attached_assembly_name
	if marker_path != "" and FileAccess.file_exists(marker_path):
		assembly_name = FileAccess.get_file_as_string(marker_path).strip_edges()
		if assembly_name == "":
			assembly_name = attached_assembly_name

	if assembly_name == "" or assembly_name == hot_reload_host.get_loaded_assembly_name():
		return

	if assembly_name == attached_assembly_name:
		hot_reload_host.use_attached_script(assembly_name)
	else:
		hot_reload_host.reload_assembly(assembly_name, reload_type_name)
