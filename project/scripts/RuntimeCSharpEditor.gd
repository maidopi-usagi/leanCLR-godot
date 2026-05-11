extends Window

const EDIT_SOURCE_PATH := "res://scripts/HotReloadSmoke.cs"
const RELOAD_MARKER_PATH := "res://leanclr/live_reload.txt"
const FRAMEWORK_RELATIVE_PATH := "../thirdparty/leanclr/src/libraries/dotnetframework4.x-linux"
const AUTORUN_ENVIRONMENT := "LEANCLR_RUNTIME_EDITOR_AUTORUN"

@onready var editor: CodeEdit = %RuntimeCSharpCodeEdit
@onready var run_button: Button = %RuntimeCSharpRunButton
@onready var status_label: Label = %RuntimeCSharpStatus

var autorun_started := false

func _ready() -> void:
	if _is_editor_scene_context():
		hide()
		return

	editor.syntax_highlighter = _create_csharp_highlighter()
	editor.text = FileAccess.get_file_as_string(EDIT_SOURCE_PATH)
	run_button.pressed.connect(compile_and_reload)
	show()

	if OS.has_feature("web"):
		run_button.disabled = true
		_set_status("Web export is read-only; runtime build is desktop only.")
		return

	if OS.has_environment(AUTORUN_ENVIRONMENT) and not autorun_started:
		autorun_started = true
		var code := editor.text
		code = code.replace('private const string Version = "flappy-v1";', 'private const string Version = "flappy-v2";')
		code = code.replace('private static readonly Color BirdColor = new Color(1.0f, 0.83f, 0.18f, 1.0f);', 'private static readonly Color BirdColor = new Color(1.0f, 0.35f, 0.18f, 1.0f);')
		code = code.replace('private const int GapCenter = 170;', 'private const int GapCenter = 130;')
		code = code.replace('public int FlapPower { get; set; } = 4;', 'public int FlapPower { get; set; } = 7;')
		editor.text = code
		compile_and_reload()

func _exit_tree() -> void:
	hide()

func _create_csharp_highlighter() -> CodeHighlighter:
	var highlighter := CodeHighlighter.new()
	highlighter.number_color = Color(0.72, 0.86, 1.0)
	highlighter.symbol_color = Color(0.86, 0.86, 0.82)
	highlighter.function_color = Color(0.55, 0.82, 1.0)
	highlighter.member_variable_color = Color(0.95, 0.75, 0.45)

	for keyword in [
		"abstract", "as", "base", "break", "case", "catch", "checked", "class", "const", "continue",
		"default", "delegate", "do", "else", "enum", "event", "explicit", "extern", "false", "finally",
		"fixed", "for", "foreach", "goto", "if", "implicit", "in", "interface", "internal", "is",
		"lock", "namespace", "new", "null", "operator", "out", "override", "params", "private", "protected",
		"public", "readonly", "ref", "return", "sealed", "sizeof", "stackalloc", "static", "struct", "switch",
		"this", "throw", "true", "try", "typeof", "unchecked", "unsafe", "using", "virtual", "void",
		"volatile", "while", "partial", "get", "set", "value", "async", "await", "yield",
	]:
		highlighter.add_keyword_color(keyword, Color(0.95, 0.48, 0.72))

	for type_keyword in [
		"bool", "byte", "char", "decimal", "double", "float", "int", "long", "object", "sbyte",
		"short", "string", "uint", "ulong", "ushort", "var", "dynamic", "Node", "Color", "Vector2",
		"Vector3", "TextureRect", "ColorRect", "Label", "FileAccess", "GD", "System",
	]:
		highlighter.add_member_keyword_color(type_keyword, Color(0.45, 0.9, 0.7))

	highlighter.add_color_region("//", "", Color(0.45, 0.55, 0.48), true)
	highlighter.add_color_region("/*", "*/", Color(0.45, 0.55, 0.48), false)
	highlighter.add_color_region("\"", "\"", Color(0.98, 0.82, 0.52), false)
	highlighter.add_color_region("'", "'", Color(0.98, 0.82, 0.52), false)
	return highlighter

func compile_and_reload() -> void:
	if editor == null:
		_set_status("Editor is not ready.")
		return
	if OS.has_feature("web"):
		_set_status("Web export is read-only; runtime build is desktop only.")
		return

	if not _write_text_file(EDIT_SOURCE_PATH, editor.text):
		_set_status("Failed to write HotReloadSmoke.cs")
		return

	var project_root := ProjectSettings.globalize_path("res://").trim_suffix("/")
	var assembly_name := "GameRuntimeEdit" + str(Time.get_unix_time_from_system()).replace(".", "")
	var project_file := project_root.path_join("Game.csproj")
	var framework_path := project_root.path_join(FRAMEWORK_RELATIVE_PATH).simplify_path()
	_set_status("Building " + assembly_name + "...")
	if not _build_assembly(project_file, assembly_name, framework_path):
		return

	var leanclr_dir := project_root.path_join("leanclr")
	var versioned_path := leanclr_dir.path_join(assembly_name + ".dll")
	var cached_versioned_path := OS.get_user_data_dir().path_join(assembly_name + ".dll")
	if not _copy_file(versioned_path, cached_versioned_path):
		_set_status("Built " + assembly_name + ", but failed to preserve the reload assembly.")
		return

	if not _build_assembly(project_file, "Game", framework_path):
		return
	if not _copy_file(cached_versioned_path, versioned_path):
		_set_status("Built Game, but failed to restore " + assembly_name + ".")
		return

	if not _write_text_file(RELOAD_MARKER_PATH, assembly_name + "\n"):
		_set_status("Built " + assembly_name + ", but failed to update reload marker.")
		return

	_set_status("Loaded marker for " + assembly_name)
	print("LeanCLR runtime editor: requested assembly = ", assembly_name)

func _build_assembly(project_file: String, assembly_name: String, framework_path: String) -> bool:
	var build_args := [
		"msbuild",
		project_file,
		"/p:Configuration=Debug",
		"/p:AssemblyName=" + assembly_name,
		"/p:OutputPath=leanclr/",
		"/p:FrameworkPathOverride=" + framework_path,
	]

	print("LeanCLR runtime editor: build command = dotnet ", " ".join(build_args))
	var output: Array = []
	var exit_code := OS.execute("dotnet", build_args, output, true, false)
	if exit_code != 0:
		_set_status("Build failed: exit code " + str(exit_code))
		printerr("LeanCLR runtime editor: build failed with exit code ", exit_code)
		for line in output:
			printerr(line)
		return false
	return true

func _copy_file(source_path: String, target_path: String) -> bool:
	var source := FileAccess.open(source_path, FileAccess.READ)
	if source == null:
		printerr("LeanCLR runtime editor: failed to open copy source ", source_path, " error = ", FileAccess.get_open_error())
		return false
	var bytes := source.get_buffer(source.get_length())
	source.close()

	var target := FileAccess.open(target_path, FileAccess.WRITE)
	if target == null:
		printerr("LeanCLR runtime editor: failed to open copy target ", target_path, " error = ", FileAccess.get_open_error())
		return false
	target.store_buffer(bytes)
	target.flush()
	target.close()
	return true

func _write_text_file(path: String, text: String) -> bool:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		printerr("LeanCLR runtime editor: failed to open ", path, " error = ", FileAccess.get_open_error())
		return false
	file.store_string(text)
	file.flush()
	file.close()
	return true

func _set_status(status: String) -> void:
	if status_label != null:
		status_label.text = status
	print("LeanCLR runtime editor: ", status)

func _is_editor_scene_context() -> bool:
	if Engine.is_editor_hint():
		return true
	var tree := get_tree()
	return tree != null and tree.edited_scene_root != null
