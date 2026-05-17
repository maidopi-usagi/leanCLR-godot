#include "leanclr_hot_reload_host.h"

#include "leanclr_runtime_bridge.h"

#include <godot_cpp/classes/engine.hpp>
#include <godot_cpp/classes/input_event.hpp>
#include <godot_cpp/classes/os.hpp>
#include <godot_cpp/classes/scene_tree.hpp>
#include <godot_cpp/variant/packed_string_array.hpp>
#include <godot_cpp/variant/node_path.hpp>
#include <godot_cpp/core/class_db.hpp>
#include <godot_cpp/variant/utility_functions.hpp>

namespace godot
{

namespace
{
bool is_editor_scene_context()
{
    Engine* engine = Engine::get_singleton();
    if (engine != nullptr && (engine->is_editor_hint()))
    {
        return true;
    }

    PackedStringArray args = OS::get_singleton()->get_cmdline_args();
    for (int32_t i = 0; i < args.size(); ++i)
    {
        if (args[i] == String("--editor") || args[i] == String("-e"))
        {
            return true;
        }
    }
    return false;
}
}

void LeanCLRHotReloadHost::_bind_methods()
{
    ClassDB::bind_method(D_METHOD("forward_input", "event"), &LeanCLRHotReloadHost::forward_input);
    ClassDB::bind_method(D_METHOD("use_attached_script", "assembly_name"), &LeanCLRHotReloadHost::use_attached_script);
    ClassDB::bind_method(D_METHOD("reload_assembly", "assembly_name", "type_name"), &LeanCLRHotReloadHost::reload_assembly);
    ClassDB::bind_method(D_METHOD("set_script_owner_path", "script_owner_path"), &LeanCLRHotReloadHost::set_script_owner_path);
    ClassDB::bind_method(D_METHOD("get_script_owner_path"), &LeanCLRHotReloadHost::get_script_owner_path);
    ClassDB::bind_method(D_METHOD("set_assembly_directory", "assembly_directory"), &LeanCLRHotReloadHost::set_assembly_directory);
    ClassDB::bind_method(D_METHOD("get_assembly_directory"), &LeanCLRHotReloadHost::get_assembly_directory);
    ClassDB::bind_method(D_METHOD("get_loaded_assembly_name"), &LeanCLRHotReloadHost::get_loaded_assembly_name);

    ADD_PROPERTY(PropertyInfo(Variant::NODE_PATH, "script_owner_path"), "set_script_owner_path", "get_script_owner_path");
    ADD_PROPERTY(PropertyInfo(Variant::STRING, "assembly_directory"), "set_assembly_directory", "get_assembly_directory");
}

LeanCLRHotReloadHost::~LeanCLRHotReloadHost()
{
    LeanCLRRuntimeBridge::release_script_object(managed_object);
    managed_object = nullptr;
}

void LeanCLRHotReloadHost::_notification(int p_what)
{
    if (p_what == NOTIFICATION_READY)
    {
        if (should_skip_runtime())
        {
            set_process(false);
            return;
        }

        set_process(true);
    }
    else if (p_what == NOTIFICATION_PROCESS)
    {
        if (should_skip_runtime())
        {
            return;
        }

        const double delta = get_process_delta_time();
        if (managed_object != nullptr)
        {
            LeanCLRRuntimeBridge::invoke_script_process(managed_object, delta);
        }
    }
}

void LeanCLRHotReloadHost::forward_input(const Ref<InputEvent>& p_event)
{
    if (!p_event.is_valid() || should_skip_runtime())
    {
        return;
    }

    void* target_object = get_active_script_object();
    if (target_object != nullptr)
    {
        LeanCLRRuntimeBridge::invoke_script_method(target_object, "_Input", p_event.ptr());
    }
}

void LeanCLRHotReloadHost::use_attached_script(const String& p_assembly_name)
{
    LeanCLRRuntimeBridge::release_script_object(managed_object);
    managed_object = nullptr;
    loaded_assembly_name = p_assembly_name;
    UtilityFunctions::print("LeanCLR live reload: using attached script assembly = ", loaded_assembly_name);
}

void LeanCLRHotReloadHost::set_script_owner_path(const NodePath& p_script_owner_path)
{
    script_owner_path = p_script_owner_path;
}

NodePath LeanCLRHotReloadHost::get_script_owner_path() const
{
    return script_owner_path;
}

void LeanCLRHotReloadHost::set_assembly_directory(const String& p_assembly_directory)
{
    LeanCLRRuntimeBridge::set_assembly_directory(p_assembly_directory);
}

String LeanCLRHotReloadHost::get_assembly_directory() const
{
    return LeanCLRRuntimeBridge::get_assembly_directory();
}

String LeanCLRHotReloadHost::get_loaded_assembly_name() const
{
    return loaded_assembly_name;
}

bool LeanCLRHotReloadHost::should_skip_runtime() const
{
    return is_editor_scene_context() || !is_inside_tree() || (get_tree() != nullptr && get_tree()->get_edited_scene_root() != nullptr);
}

Object* LeanCLRHotReloadHost::get_script_owner() const
{
    if (!script_owner_path.is_empty())
    {
        Node* owner = get_node_or_null(script_owner_path);
        if (owner != nullptr)
        {
            return owner;
        }
    }

    return const_cast<LeanCLRHotReloadHost*>(this);
}

void* LeanCLRHotReloadHost::get_attached_script_object() const
{
    Object* owner = get_script_owner();
    return owner != nullptr ? LeanCLRRuntimeBridge::get_script_object_for_owner(owner) : nullptr;
}

void* LeanCLRHotReloadHost::get_active_script_object() const
{
    return managed_object != nullptr ? managed_object : get_attached_script_object();
}

bool LeanCLRHotReloadHost::reload_assembly(const String& p_assembly_name, const String& p_type_name)
{
    if (p_assembly_name.is_empty() || p_type_name.is_empty())
    {
        UtilityFunctions::printerr("LeanCLR live reload: assembly_name and type_name are required.");
        return false;
    }

    Object* owner = get_script_owner();
    void* previous_object = get_active_script_object();
    Variant custom_state;
    const bool has_custom_state = previous_object != nullptr &&
                                  LeanCLRRuntimeBridge::has_script_method(previous_object, "CaptureHotReloadState", 0) &&
                                  LeanCLRRuntimeBridge::invoke_script_method(previous_object, "CaptureHotReloadState", nullptr, 0, &custom_state);

    void* next_object = LeanCLRRuntimeBridge::create_script_object(p_assembly_name, p_type_name, owner);
    if (next_object == nullptr)
    {
        UtilityFunctions::printerr("LeanCLR live reload: failed to load ", p_assembly_name, ": ", LeanCLRRuntimeBridge::get_last_error());
        return false;
    }

    const int32_t migrated_fields = LeanCLRRuntimeBridge::migrate_script_state(previous_object, next_object);
    if (has_custom_state && LeanCLRRuntimeBridge::has_script_method(next_object, "RestoreHotReloadState", 1))
    {
        LeanCLRRuntimeBridge::invoke_script_method(next_object, "RestoreHotReloadState", custom_state);
    }

    if (managed_object != nullptr)
    {
        LeanCLRRuntimeBridge::release_script_object(managed_object);
    }
    managed_object = next_object;
    loaded_assembly_name = p_assembly_name;

    UtilityFunctions::print("LeanCLR live reload: loaded assembly = ", loaded_assembly_name);
    UtilityFunctions::print("LeanCLR live reload: migrated fields = ", migrated_fields);
    LeanCLRRuntimeBridge::invoke_script_ready(managed_object);
    LeanCLRRuntimeBridge::invoke_script_method(managed_object, "OnHotReloaded");
    return true;
}

} // namespace godot
