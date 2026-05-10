#include "leanclr_script_saver.h"

#include "leanclr_script.h"

#include <godot_cpp/classes/file_access.hpp>
#include <godot_cpp/classes/resource.hpp>
#include <godot_cpp/core/class_db.hpp>
#include <godot_cpp/variant/utility_functions.hpp>

namespace godot
{

void LeanCLRScriptSaver::_bind_methods()
{
}

Error LeanCLRScriptSaver::_save(const Ref<Resource>& p_resource, const String& p_path, uint32_t p_flags)
{
    (void)p_flags;
    LeanCLRScript* script = Object::cast_to<LeanCLRScript>(p_resource.ptr());
    if (script == nullptr || p_path.is_empty())
    {
        return ERR_INVALID_PARAMETER;
    }

    String source_code = script->_get_source_code();
    if (source_code.is_empty() && FileAccess::file_exists(p_path))
    {
        source_code = FileAccess::get_file_as_string(p_path);
    }

    Ref<FileAccess> file = FileAccess::open(p_path, FileAccess::WRITE);
    if (!file.is_valid())
    {
        const Error error = FileAccess::get_open_error();
        UtilityFunctions::printerr("LeanCLR script saver: failed to open ", p_path, " error = ", static_cast<int64_t>(error));
        return error;
    }

    file->store_string(source_code);
    file->flush();
    file->close();
    return OK;
}

Error LeanCLRScriptSaver::_set_uid(const String& p_path, int64_t p_uid)
{
    (void)p_path;
    (void)p_uid;
    return OK;
}

bool LeanCLRScriptSaver::_recognize(const Ref<Resource>& p_resource) const
{
    return Object::cast_to<LeanCLRScript>(p_resource.ptr()) != nullptr;
}

PackedStringArray LeanCLRScriptSaver::_get_recognized_extensions(const Ref<Resource>& p_resource) const
{
    PackedStringArray extensions;
    if (_recognize(p_resource))
    {
        extensions.push_back("cs");
        extensions.push_back("lcs");
    }
    return extensions;
}

bool LeanCLRScriptSaver::_recognize_path(const Ref<Resource>& p_resource, const String& p_path) const
{
    if (!_recognize(p_resource))
    {
        return false;
    }
    const String extension = p_path.get_extension().to_lower();
    return extension == "cs" || extension == "lcs";
}

} // namespace godot
