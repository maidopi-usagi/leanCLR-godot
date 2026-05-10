#include "leanclr_hot_reload_host.h"

#include "leanclr_runtime_bridge.h"

#include <godot_cpp/classes/engine.hpp>
#include <godot_cpp/classes/file_access.hpp>
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
const char* RELOAD_MARKER_PATH = "res://leanclr/live_reload.txt";
const char* RELOAD_TYPE_NAME = "Game.HotReloadSmoke";

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
        if (is_editor_scene_context() || !is_inside_tree() || (get_tree() != nullptr && get_tree()->get_edited_scene_root() != nullptr))
        {
            set_process(false);
            return;
        }

        set_process(true);
        check_reload_marker();
    }
    else if (p_what == NOTIFICATION_PROCESS)
    {
        if (is_editor_scene_context() || !is_inside_tree() || (get_tree() != nullptr && get_tree()->get_edited_scene_root() != nullptr))
        {
            return;
        }

        const double delta = get_process_delta_time();
        if (managed_object != nullptr)
        {
            LeanCLRRuntimeBridge::invoke_script_process(managed_object, delta);
        }

        elapsed += delta;
        if (elapsed >= 0.25)
        {
            elapsed = 0.0;
            check_reload_marker();
        }
    }
}

void LeanCLRHotReloadHost::forward_input(const Ref<InputEvent>& p_event)
{
    if (managed_object == nullptr || !p_event.is_valid() || is_editor_scene_context() || !is_inside_tree() ||
        (get_tree() != nullptr && get_tree()->get_edited_scene_root() != nullptr))
    {
        return;
    }

    LeanCLRRuntimeBridge::invoke_script_method(managed_object, "_Input", p_event.ptr());
}

void LeanCLRHotReloadHost::check_reload_marker()
{
    String assembly_name = "Game";
    if (FileAccess::file_exists(RELOAD_MARKER_PATH))
    {
        assembly_name = FileAccess::get_file_as_string(RELOAD_MARKER_PATH).strip_edges();
        if (assembly_name.is_empty())
        {
            assembly_name = "Game";
        }
    }

    if (assembly_name == loaded_assembly_name)
    {
        return;
    }

    reload_managed_object(assembly_name);
}

void LeanCLRHotReloadHost::reload_managed_object(const String& p_assembly_name)
{
    if (p_assembly_name == String("Game"))
    {
        LeanCLRRuntimeBridge::release_script_object(managed_object);
        managed_object = nullptr;
        loaded_assembly_name = p_assembly_name;
        UtilityFunctions::print("LeanCLR live reload: using attached script assembly = ", loaded_assembly_name);
        return;
    }

    Object* owner = this;
    Node* parent = get_parent();
    if (parent != nullptr)
    {
        Node* script_owner = parent->get_node_or_null(NodePath("FlappyScript"));
        if (script_owner != nullptr)
        {
            owner = script_owner;
        }
    }

    void* previous_object = managed_object != nullptr ? managed_object : LeanCLRRuntimeBridge::get_script_object_for_owner(owner);
    Variant custom_state;
    const bool has_custom_state = previous_object != nullptr &&
                                  LeanCLRRuntimeBridge::has_script_method(previous_object, "CaptureHotReloadState", 0) &&
                                  LeanCLRRuntimeBridge::invoke_script_method(previous_object, "CaptureHotReloadState", nullptr, 0, &custom_state);

    void* next_object = LeanCLRRuntimeBridge::create_script_object(p_assembly_name, RELOAD_TYPE_NAME, owner);
    if (next_object == nullptr)
    {
        UtilityFunctions::printerr("LeanCLR live reload: failed to load ", p_assembly_name, ": ", LeanCLRRuntimeBridge::get_last_error());
        return;
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
}

} // namespace godot
