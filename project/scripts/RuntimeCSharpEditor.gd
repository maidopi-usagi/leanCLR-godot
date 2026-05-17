extends Window

const EDIT_SOURCE_PATH := "res://scripts/HotReloadSmoke.cs"
const RELOAD_MARKER_PATH := "res://leanclr/live_reload.txt"
const FRAMEWORK_RELATIVE_PATH := "../thirdparty/leanclr/src/libraries/dotnetframework4.x-linux"
const AUTORUN_ENVIRONMENT := "LEANCLR_RUNTIME_EDITOR_AUTORUN"
const WEB_ASSEMBLY_DIRECTORY := "user://leanclr"
const WEB_RELOAD_TYPE_NAME := "Game.HotReloadSmoke"
const WEB_DEPENDENCY_ASSEMBLIES := ["mscorlib.dll", "System.dll", "GodotSharpCompat.dll"]

@onready var editor: CodeEdit = %RuntimeCSharpCodeEdit
@onready var run_button: Button = %RuntimeCSharpRunButton
@onready var status_label: Label = %RuntimeCSharpStatus

var autorun_started := false
var pending_web_assembly_name := ""
var web_compile_polling := false

func _ready() -> void:
	if _is_editor_scene_context():
		hide()
		return

	editor.syntax_highlighter = _create_csharp_highlighter()
	editor.text = FileAccess.get_file_as_string(EDIT_SOURCE_PATH)
	run_button.pressed.connect(compile_and_reload)
	show()

	if OS.has_feature("web"):
		set_process(true)
		_set_status("Web Roslyn sidecar ready check...")
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

func _process(_delta: float) -> void:
	if web_compile_polling:
		_poll_web_compile_result()

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
		compile_and_reload_web()
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

func compile_and_reload_web() -> void:
	if web_compile_polling:
		_set_status("Web compiler is already building.")
		return
	if not _prepare_web_assembly_directory():
		return

	pending_web_assembly_name = "GameRuntimeEdit" + str(Time.get_unix_time_from_system()).replace(".", "")
	var arguments_json := JSON.stringify([pending_web_assembly_name, editor.text])
	var script := """
(function(args) {
  if (!window.LeanCLR || typeof window.LeanCLR.compileCSharp !== 'function') {
    window.LeanCLRGodotCompileResult = { state: 'error', message: 'Roslyn sidecar is not loaded yet.' };
    return;
  }
  window.LeanCLRGodotCompileResult = { state: 'building', assemblyName: args[0] };
  window.LeanCLR.compileCSharp(args[0], args[1]).then(function(result) {
    window.LeanCLRGodotCompileResult = result;
  }).catch(function(error) {
    window.LeanCLRGodotCompileResult = { state: 'error', message: String(error && error.stack ? error.stack : error) };
  });
})(%s);
""" % arguments_json
	JavaScriptBridge.eval(script)
	web_compile_polling = true
	_set_status("Building " + pending_web_assembly_name + " in browser Roslyn sidecar...")

func _poll_web_compile_result() -> void:
	var result_json := str(JavaScriptBridge.eval("JSON.stringify(window.LeanCLRGodotCompileResult || { state: 'idle' })"))
	var parsed := JSON.parse_string(result_json)
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	var state := str(parsed.get("state", "idle"))
	if state == "idle" or state == "building":
		return
	web_compile_polling = false
	if state != "ok":
		var message := str(parsed.get("message", "unknown compile error"))
		_set_status("Web build failed: " + message.substr(0, 180))
		printerr("LeanCLR runtime editor: web build failed: ", message)
		return

	var assembly_name := str(parsed.get("assemblyName", ""))
	if assembly_name == "":
		assembly_name = pending_web_assembly_name
	if assembly_name == "":
		_set_status("Web build failed: missing assembly name.")
		return
	var dll_base64 := str(parsed.get("dllBase64", ""))
	if dll_base64 == "":
		_set_status("Web build failed: compiler returned no DLL.")
		return

	var assembly_path := WEB_ASSEMBLY_DIRECTORY.path_join(assembly_name + ".dll")
	var assembly_bytes := Marshalls.base64_to_raw(dll_base64)
	var file := FileAccess.open(assembly_path, FileAccess.WRITE)
	if file == null:
		_set_status("Built " + assembly_name + ", but failed to write DLL to user://.")
		printerr("LeanCLR runtime editor: failed to write ", assembly_path, " error = ", FileAccess.get_open_error())
		return
	file.store_buffer(assembly_bytes)
	file.flush()
	file.close()

	var hot_reload_host := get_node_or_null("../LiveHotReloadHost")
	if hot_reload_host == null:
		_set_status("Built " + assembly_name + ", but LiveHotReloadHost was not found.")
		return
	_stop_marker_polling_for_web_reload()
	hot_reload_host.set_assembly_directory(WEB_ASSEMBLY_DIRECTORY)
	if hot_reload_host.reload_assembly(assembly_name, WEB_RELOAD_TYPE_NAME):
		_activate_web_reload_owner()
		_set_status("Loaded " + assembly_name + " from browser storage")
		print("LeanCLR runtime editor: web loaded assembly = ", assembly_name)
	else:
		_set_status("Built " + assembly_name + ", but reload failed.")

func _prepare_web_assembly_directory() -> bool:
	var dir := DirAccess.open("user://")
	if dir == null:
		_set_status("Failed to open user:// for web assemblies.")
		return false
	var error := dir.make_dir_recursive("leanclr")
	if error != OK and error != ERR_ALREADY_EXISTS:
		_set_status("Failed to create user://leanclr: " + str(error))
		return false
	for dependency: String in WEB_DEPENDENCY_ASSEMBLIES:
		var source_path := "res://leanclr/" + dependency
		var target_path := WEB_ASSEMBLY_DIRECTORY.path_join(dependency)
		if not FileAccess.file_exists(target_path) and not _copy_file(source_path, target_path):
			_set_status("Failed to copy " + dependency + " to browser storage.")
			return false
	return true

func _stop_marker_polling_for_web_reload() -> void:
	var relay := get_node_or_null("../HotReloadInputRelay")
	if relay != null:
		relay.set_process(false)

func _activate_web_reload_owner() -> void:
	var owner := get_node_or_null("../FlappyScript")
	if owner != null:
		owner.set_meta(&"leanclr_runtime_reload_active", true)

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
