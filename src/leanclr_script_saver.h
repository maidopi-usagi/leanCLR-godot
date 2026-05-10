#pragma once

#include <godot_cpp/classes/resource_format_saver.hpp>

namespace godot
{

class LeanCLRScriptSaver : public ResourceFormatSaver
{
    GDCLASS(LeanCLRScriptSaver, ResourceFormatSaver)

  public:
    Error _save(const Ref<Resource>& p_resource, const String& p_path, uint32_t p_flags) override;
    Error _set_uid(const String& p_path, int64_t p_uid) override;
    bool _recognize(const Ref<Resource>& p_resource) const override;
    PackedStringArray _get_recognized_extensions(const Ref<Resource>& p_resource) const override;
    bool _recognize_path(const Ref<Resource>& p_resource, const String& p_path) const override;

  protected:
    static void _bind_methods();
};

} // namespace godot
