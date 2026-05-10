#include "leanclr_script_language.h"

#include "leanclr_runtime_bridge.h"
#include "leanclr_script.h"

#include <godot_cpp/classes/engine.hpp>
#include <godot_cpp/classes/file_access.hpp>
#include <godot_cpp/core/class_db.hpp>
#include <godot_cpp/core/memory.hpp>
#include <godot_cpp/variant/array.hpp>
#include <godot_cpp/variant/packed_string_array.hpp>

namespace godot
{

LeanCLRScriptLanguage* LeanCLRScriptLanguage::singleton = nullptr;

void LeanCLRScriptLanguage::_bind_methods()
{
}

void LeanCLRScriptLanguage::init_singleton()
{
    if (singleton != nullptr)
    {
        return;
    }

    singleton = memnew(LeanCLRScriptLanguage);
    Engine::get_singleton()->register_script_language(singleton);
}

void LeanCLRScriptLanguage::deinit_singleton()
{
    if (singleton == nullptr)
    {
        return;
    }

    Engine::get_singleton()->unregister_script_language(singleton);
    memdelete(singleton);
    singleton = nullptr;
}

LeanCLRScriptLanguage* LeanCLRScriptLanguage::get_singleton()
{
    return singleton;
}

String LeanCLRScriptLanguage::_get_name() const
{
    return "LeanCLR C#";
}

void LeanCLRScriptLanguage::_init()
{
}

String LeanCLRScriptLanguage::_get_type() const
{
    return "LeanCLRScript";
}

String LeanCLRScriptLanguage::_get_extension() const
{
    return "cs";
}

void LeanCLRScriptLanguage::_finish()
{
    LeanCLRRuntimeBridge::shutdown();
}

PackedStringArray LeanCLRScriptLanguage::_get_reserved_words() const
{
    PackedStringArray words;
    words.push_back("assembly");
    words.push_back("type");
    words.push_back("base");
    words.push_back("entry");
    return words;
}

bool LeanCLRScriptLanguage::_is_control_flow_keyword(const String& p_keyword) const
{
    (void)p_keyword;
    return false;
}

PackedStringArray LeanCLRScriptLanguage::_get_comment_delimiters() const
{
    PackedStringArray delimiters;
    delimiters.push_back("#");
    delimiters.push_back("//");
    return delimiters;
}

PackedStringArray LeanCLRScriptLanguage::_get_doc_comment_delimiters() const
{
    return PackedStringArray();
}

PackedStringArray LeanCLRScriptLanguage::_get_string_delimiters() const
{
    PackedStringArray delimiters;
    delimiters.push_back("\"");
    return delimiters;
}

Ref<Script> LeanCLRScriptLanguage::_make_template(const String& p_template, const String& p_class_name, const String& p_base_class_name) const
{
    (void)p_template;
    Ref<LeanCLRScript> script;
    script.instantiate();
    script->_set_source_code("using Godot;\n\nnamespace Game;\n\npublic partial class " + p_class_name + " : " + p_base_class_name + "\n{\n}\n");
    return script;
}

TypedArray<Dictionary> LeanCLRScriptLanguage::_get_built_in_templates(const StringName& p_object) const
{
    (void)p_object;
    return TypedArray<Dictionary>();
}

bool LeanCLRScriptLanguage::_is_using_templates()
{
    return true;
}

Dictionary LeanCLRScriptLanguage::_validate(const String& p_script, const String& p_path, bool p_validate_functions, bool p_validate_errors,
                                            bool p_validate_warnings, bool p_validate_safe_lines) const
{
    (void)p_validate_functions;
    (void)p_validate_warnings;
    (void)p_validate_safe_lines;

    const bool is_cs = p_path.get_extension().to_lower() == "cs";
    const bool has_assembly = p_script.find("assembly=") >= 0;
    const bool has_type = p_script.find("type=") >= 0;
    Dictionary result;
    result["valid"] = is_cs || (has_assembly && has_type);

    if (p_validate_errors && !is_cs && !(has_assembly && has_type))
    {
        Array errors;
        Dictionary error;
        error["path"] = p_path;
        error["line"] = 1;
        error["column"] = 1;
        error["message"] = "LeanCLR script requires assembly=<name> and type=<namespace.type>.";
        errors.push_back(error);
        result["errors"] = errors;
    }

    return result;
}

String LeanCLRScriptLanguage::_validate_path(const String& p_path) const
{
    const String extension = p_path.get_extension().to_lower();
    return extension == "cs" || extension == "lcs" ? String() : String("LeanCLR scripts must use .cs or .lcs extension.");
}

Object* LeanCLRScriptLanguage::_create_script() const
{
    return memnew(LeanCLRScript);
}

bool LeanCLRScriptLanguage::_has_named_classes() const
{
    return true;
}

bool LeanCLRScriptLanguage::_supports_builtin_mode() const
{
    return false;
}

bool LeanCLRScriptLanguage::_supports_documentation() const
{
    return false;
}

bool LeanCLRScriptLanguage::_can_inherit_from_file() const
{
    return false;
}

int32_t LeanCLRScriptLanguage::_find_function(const String& p_function, const String& p_code) const
{
    (void)p_function;
    (void)p_code;
    return -1;
}

String LeanCLRScriptLanguage::_make_function(const String& p_class_name, const String& p_function_name, const PackedStringArray& p_function_args) const
{
    (void)p_class_name;
    (void)p_function_name;
    (void)p_function_args;
    return String();
}

bool LeanCLRScriptLanguage::_can_make_function() const
{
    return false;
}

Error LeanCLRScriptLanguage::_open_in_external_editor(const Ref<Script>& p_script, int32_t p_line, int32_t p_column)
{
    (void)p_script;
    (void)p_line;
    (void)p_column;
    return ERR_UNAVAILABLE;
}

bool LeanCLRScriptLanguage::_overrides_external_editor()
{
    return false;
}

ScriptLanguage::ScriptNameCasing LeanCLRScriptLanguage::_preferred_file_name_casing() const
{
    return SCRIPT_NAME_CASING_PASCAL_CASE;
}

Dictionary LeanCLRScriptLanguage::_complete_code(const String& p_code, const String& p_path, Object* p_owner) const
{
    (void)p_code;
    (void)p_path;
    (void)p_owner;
    Dictionary result;
    result["result"] = ERR_UNAVAILABLE;
    result["force"] = false;
    result["call_hint"] = String();
    return result;
}

Dictionary LeanCLRScriptLanguage::_lookup_code(const String& p_code, const String& p_symbol, const String& p_path, Object* p_owner) const
{
    (void)p_code;
    (void)p_symbol;
    (void)p_path;
    (void)p_owner;
    Dictionary result;
    result["result"] = ERR_UNAVAILABLE;
    result["type"] = LOOKUP_RESULT_SCRIPT_LOCATION;
    return result;
}

String LeanCLRScriptLanguage::_auto_indent_code(const String& p_code, int32_t p_from_line, int32_t p_to_line) const
{
    (void)p_from_line;
    (void)p_to_line;
    return p_code;
}

void LeanCLRScriptLanguage::_thread_enter()
{
}

void LeanCLRScriptLanguage::_thread_exit()
{
}

String LeanCLRScriptLanguage::_debug_get_error() const
{
    return LeanCLRRuntimeBridge::get_last_error();
}

int32_t LeanCLRScriptLanguage::_debug_get_stack_level_count() const
{
    return 0;
}

int32_t LeanCLRScriptLanguage::_debug_get_stack_level_line(int32_t p_level) const
{
    (void)p_level;
    return -1;
}

String LeanCLRScriptLanguage::_debug_get_stack_level_function(int32_t p_level) const
{
    (void)p_level;
    return String();
}

String LeanCLRScriptLanguage::_debug_get_stack_level_source(int32_t p_level) const
{
    (void)p_level;
    return String();
}

Dictionary LeanCLRScriptLanguage::_debug_get_stack_level_locals(int32_t p_level, int32_t p_max_subitems, int32_t p_max_depth)
{
    (void)p_level;
    (void)p_max_subitems;
    (void)p_max_depth;
    return Dictionary();
}

Dictionary LeanCLRScriptLanguage::_debug_get_stack_level_members(int32_t p_level, int32_t p_max_subitems, int32_t p_max_depth)
{
    (void)p_level;
    (void)p_max_subitems;
    (void)p_max_depth;
    return Dictionary();
}

void* LeanCLRScriptLanguage::_debug_get_stack_level_instance(int32_t p_level)
{
    (void)p_level;
    return nullptr;
}

Dictionary LeanCLRScriptLanguage::_debug_get_globals(int32_t p_max_subitems, int32_t p_max_depth)
{
    (void)p_max_subitems;
    (void)p_max_depth;
    return Dictionary();
}

String LeanCLRScriptLanguage::_debug_parse_stack_level_expression(int32_t p_level, const String& p_expression, int32_t p_max_subitems, int32_t p_max_depth)
{
    (void)p_level;
    (void)p_expression;
    (void)p_max_subitems;
    (void)p_max_depth;
    return String();
}

TypedArray<Dictionary> LeanCLRScriptLanguage::_debug_get_current_stack_info()
{
    return TypedArray<Dictionary>();
}

void LeanCLRScriptLanguage::_reload_all_scripts()
{
}

void LeanCLRScriptLanguage::_reload_scripts(const Array& p_scripts, bool p_soft_reload)
{
    (void)p_scripts;
    (void)p_soft_reload;
}

void LeanCLRScriptLanguage::_reload_tool_script(const Ref<Script>& p_script, bool p_soft_reload)
{
    (void)p_script;
    (void)p_soft_reload;
}

PackedStringArray LeanCLRScriptLanguage::_get_recognized_extensions() const
{
    PackedStringArray extensions;
    extensions.push_back("cs");
    extensions.push_back("lcs");
    return extensions;
}

TypedArray<Dictionary> LeanCLRScriptLanguage::_get_public_functions() const
{
    return TypedArray<Dictionary>();
}

Dictionary LeanCLRScriptLanguage::_get_public_constants() const
{
    return Dictionary();
}

TypedArray<Dictionary> LeanCLRScriptLanguage::_get_public_annotations() const
{
    return TypedArray<Dictionary>();
}

void LeanCLRScriptLanguage::_profiling_start()
{
}

void LeanCLRScriptLanguage::_profiling_stop()
{
}

void LeanCLRScriptLanguage::_profiling_set_save_native_calls(bool p_enable)
{
    (void)p_enable;
}

int32_t LeanCLRScriptLanguage::_profiling_get_accumulated_data(ScriptLanguageExtensionProfilingInfo* p_info_array, int32_t p_info_max)
{
    (void)p_info_array;
    (void)p_info_max;
    return 0;
}

int32_t LeanCLRScriptLanguage::_profiling_get_frame_data(ScriptLanguageExtensionProfilingInfo* p_info_array, int32_t p_info_max)
{
    (void)p_info_array;
    (void)p_info_max;
    return 0;
}

void LeanCLRScriptLanguage::_frame()
{
}

bool LeanCLRScriptLanguage::_handles_global_class_type(const String& p_type) const
{
    return p_type == "LeanCLRScript";
}

Dictionary LeanCLRScriptLanguage::_get_global_class_name(const String& p_path) const
{
    Dictionary result;
    const String extension = p_path.get_extension().to_lower();
    if (extension != "cs" && extension != "lcs")
    {
        return result;
    }

    const String source = FileAccess::get_file_as_string(p_path);
    Ref<LeanCLRScript> script;
    script.instantiate();
    script->set_path_hint(p_path);
    script->_set_source_code(source);
    if (script->_is_valid())
    {
        result["name"] = script->get_type_name();
        result["base_type"] = script->_get_instance_base_type();
        return result;
    }

    PackedStringArray lines = source.split("\n");
    for (int64_t i = 0; i < lines.size(); ++i)
    {
        PackedStringArray pair = lines[i].strip_edges().split("=", false, 1);
        if (pair.size() != 2)
        {
            continue;
        }

        const String key = pair[0].strip_edges().to_lower();
        const String value = pair[1].strip_edges();
        if (key == "type")
        {
            result["name"] = value;
        }
        else if (key == "base")
        {
            result["base_type"] = value;
        }
    }

    return result;
}

} // namespace godot
