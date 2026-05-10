#include "leanclr_script_loader.h"

#include "leanclr_script.h"

#include <godot_cpp/classes/file_access.hpp>
#include <godot_cpp/core/class_db.hpp>

namespace godot
{

void LeanCLRScriptLoader::_bind_methods()
{
}

PackedStringArray LeanCLRScriptLoader::_get_recognized_extensions() const
{
    PackedStringArray extensions;
    extensions.push_back("cs");
    extensions.push_back("lcs");
    return extensions;
}

bool LeanCLRScriptLoader::_handles_type(const StringName& p_type) const
{
    return p_type == StringName("Script") || p_type == StringName("LeanCLRScript") || p_type == StringName();
}

String LeanCLRScriptLoader::_get_resource_type(const String& p_path) const
{
    const String extension = p_path.get_extension().to_lower();
    return extension == "cs" || extension == "lcs" ? String("LeanCLRScript") : String();
}

Variant LeanCLRScriptLoader::_load(const String& p_path, const String& p_original_path, bool p_use_sub_threads, int32_t p_cache_mode) const
{
    (void)p_original_path;
    (void)p_use_sub_threads;
    (void)p_cache_mode;

    Ref<LeanCLRScript> script;
    script.instantiate();
    script->set_path_hint(p_path);
    script->_set_source_code(FileAccess::get_file_as_string(p_path));

    const Error reload_error = script->_reload(false);
    if (reload_error != OK)
    {
        return reload_error;
    }

    return script;
}

} // namespace godot
