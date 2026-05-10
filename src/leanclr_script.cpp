#include "leanclr_script.h"

#include "leanclr_runtime_bridge.h"
#include "leanclr_script_language.h"

#include <godot_cpp/classes/engine.hpp>
#include <godot_cpp/classes/script_language.hpp>
#include <godot_cpp/classes/scene_tree.hpp>
#include <godot_cpp/classes/input_event.hpp>
#include <godot_cpp/classes/node.hpp>
#include <godot_cpp/classes/os.hpp>
#include <godot_cpp/core/class_db.hpp>
#include <godot_cpp/core/gdextension_interface_loader.hpp>
#include <godot_cpp/variant/packed_string_array.hpp>
#include <godot_cpp/variant/string_name.hpp>
#include <godot_cpp/variant/variant.hpp>
#include <godot_cpp/variant/string.hpp>

#include <gdextension_interface.h>

#include <vector>

namespace godot
{

namespace
{

struct LeanCLRScriptInstance
{
    Object* owner = nullptr;
    Ref<LeanCLRScript> script;
    void* managed_object = nullptr;
    bool ready_invoked = false;
};

LeanCLRScriptInstance* as_instance(GDExtensionScriptInstanceDataPtr p_instance)
{
    return static_cast<LeanCLRScriptInstance*>(p_instance);
}

String pascal_virtual_name(const StringName& p_godot_method)
{
    const String source = String(p_godot_method);
    if (!source.begins_with("_"))
    {
        return String();
    }

    String result = "_";
    PackedStringArray parts = source.substr(1).split("_");
    for (int32_t i = 0; i < parts.size(); ++i)
    {
        String part = parts[i];
        if (part.is_empty())
        {
            continue;
        }
        if (part == "2d")
        {
            result += "2D";
        }
        else if (part == "3d")
        {
            result += "3D";
        }
        else if (part == "gui")
        {
            result += "Gui";
        }
        else if (part == "rid")
        {
            result += "Rid";
        }
        else
        {
            result += part.substr(0, 1).to_upper() + part.substr(1);
        }
    }
    return result;
}

String managed_virtual_name(const StringName& p_godot_method)
{
    return pascal_virtual_name(p_godot_method);
}


bool is_editor_scene_context(Object* p_owner = nullptr)
{
    Node* owner_node = Object::cast_to<Node>(p_owner);
    if (owner_node != nullptr && owner_node->is_inside_tree() && owner_node->get_tree() != nullptr && owner_node->get_tree()->get_edited_scene_root() != nullptr)
    {
        return true;
    }

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

int32_t managed_virtual_argument_count(const StringName& p_godot_method)
{
    if (p_godot_method == StringName("_process") || p_godot_method == StringName("_physics_process") || p_godot_method == StringName("_input") ||
        p_godot_method == StringName("_gui_input") || p_godot_method == StringName("_shortcut_input") || p_godot_method == StringName("_unhandled_input") ||
        p_godot_method == StringName("_unhandled_key_input") || p_godot_method == StringName("_set_path_cache") ||
        p_godot_method == StringName("_make_visible") || p_godot_method == StringName("_edit") || p_godot_method == StringName("_handles") ||
        p_godot_method == StringName("_set_state") || p_godot_method == StringName("_get_unsaved_status") || p_godot_method == StringName("_set_window_layout") ||
        p_godot_method == StringName("_get_window_layout") || p_godot_method == StringName("_forward_canvas_gui_input") ||
        p_godot_method == StringName("_forward_canvas_draw_over_viewport") || p_godot_method == StringName("_forward_canvas_force_draw_over_viewport") ||
        p_godot_method == StringName("_forward_3d_draw_over_viewport") || p_godot_method == StringName("_forward_3d_force_draw_over_viewport") ||
        p_godot_method == StringName("_run_scene") || p_godot_method == StringName("_has_point") || p_godot_method == StringName("_get_tooltip") ||
        p_godot_method == StringName("_get_drag_data") || p_godot_method == StringName("_make_custom_tooltip") ||
        p_godot_method == StringName("_get_accessibility_container_name"))
    {
        return 1;
    }
    if (p_godot_method == StringName("_forward_3d_gui_input") || p_godot_method == StringName("_structured_text_parser") ||
        p_godot_method == StringName("_can_drop_data") || p_godot_method == StringName("_drop_data"))
    {
        return 2;
    }
    return 0;
}

GDExtensionBool script_instance_set(GDExtensionScriptInstanceDataPtr p_instance, GDExtensionConstStringNamePtr p_name,
                                    GDExtensionConstVariantPtr p_value)
{
    LeanCLRScriptInstance* instance = as_instance(p_instance);
    const StringName& name = *reinterpret_cast<const StringName*>(p_name);
    const Variant& value = *reinterpret_cast<const Variant*>(p_value);
    return LeanCLRRuntimeBridge::set_script_property(instance->managed_object, String(name), value);
}

GDExtensionBool script_instance_get(GDExtensionScriptInstanceDataPtr p_instance, GDExtensionConstStringNamePtr p_name, GDExtensionVariantPtr r_ret)
{
    LeanCLRScriptInstance* instance = as_instance(p_instance);
    const StringName& name = *reinterpret_cast<const StringName*>(p_name);
    Variant value;
    if (!LeanCLRRuntimeBridge::get_script_property(instance->managed_object, String(name), &value))
    {
        *reinterpret_cast<Variant*>(r_ret) = Variant();
        return false;
    }
    *reinterpret_cast<Variant*>(r_ret) = value;
    return true;
}

const GDExtensionPropertyInfo* script_instance_get_property_list(GDExtensionScriptInstanceDataPtr p_instance, uint32_t* r_count)
{
    LeanCLRScriptInstance* instance = as_instance(p_instance);
    std::vector<LeanCLRScriptPropertyInfo> properties;
    if (!LeanCLRRuntimeBridge::get_script_property_list(instance->managed_object, properties) || properties.empty())
    {
        *r_count = 0;
        return nullptr;
    }

    GDExtensionPropertyInfo* list = new GDExtensionPropertyInfo[properties.size()];
    for (size_t i = 0; i < properties.size(); ++i)
    {
        list[i].type = static_cast<GDExtensionVariantType>(properties[i].type);
        list[i].name = reinterpret_cast<GDExtensionStringNamePtr>(new StringName(properties[i].name));
        list[i].class_name = reinterpret_cast<GDExtensionStringNamePtr>(new StringName());
        list[i].hint = properties[i].hint;
        list[i].hint_string = reinterpret_cast<GDExtensionStringPtr>(new String(properties[i].hint_string));
        list[i].usage = properties[i].usage;
    }
    *r_count = static_cast<uint32_t>(properties.size());
    return list;
}

void script_instance_free_property_list(GDExtensionScriptInstanceDataPtr p_instance, const GDExtensionPropertyInfo* p_list, uint32_t p_count)
{
    (void)p_instance;
    for (uint32_t i = 0; i < p_count; ++i)
    {
        delete reinterpret_cast<StringName*>(p_list[i].name);
        delete reinterpret_cast<StringName*>(p_list[i].class_name);
        delete reinterpret_cast<String*>(p_list[i].hint_string);
    }
    delete[] p_list;
}

GDExtensionObjectPtr script_instance_get_owner(GDExtensionScriptInstanceDataPtr p_instance)
{
    LeanCLRScriptInstance* instance = as_instance(p_instance);
    return instance->owner != nullptr ? instance->owner->_owner : nullptr;
}

void script_instance_get_property_state(GDExtensionScriptInstanceDataPtr p_instance, GDExtensionScriptInstancePropertyStateAdd p_add_func,
                                        void* p_userdata)
{
    LeanCLRScriptInstance* instance = as_instance(p_instance);
    std::vector<LeanCLRScriptPropertyInfo> properties;
    LeanCLRRuntimeBridge::get_script_property_list(instance->managed_object, properties);
    for (size_t i = 0; i < properties.size(); ++i)
    {
        StringName name(properties[i].name);
        Variant value;
        if (LeanCLRRuntimeBridge::get_script_property(instance->managed_object, properties[i].name, &value))
        {
            p_add_func(&name, &value, p_userdata);
        }
    }
}

const GDExtensionMethodInfo* script_instance_get_method_list(GDExtensionScriptInstanceDataPtr p_instance, uint32_t* r_count)
{
    (void)p_instance;
    *r_count = 0;
    return nullptr;
}

void script_instance_free_method_list(GDExtensionScriptInstanceDataPtr p_instance, const GDExtensionMethodInfo* p_list, uint32_t p_count)
{
    (void)p_instance;
    (void)p_list;
    (void)p_count;
}

GDExtensionVariantType script_instance_get_property_type(GDExtensionScriptInstanceDataPtr p_instance, GDExtensionConstStringNamePtr p_name,
                                                         GDExtensionBool* r_is_valid)
{
    LeanCLRScriptInstance* instance = as_instance(p_instance);
    const StringName& name = *reinterpret_cast<const StringName*>(p_name);
    bool is_valid = false;
    int32_t type = LeanCLRRuntimeBridge::get_script_property_type(instance->managed_object, String(name), &is_valid);
    *r_is_valid = is_valid;
    return static_cast<GDExtensionVariantType>(type);
}

GDExtensionBool script_instance_has_method(GDExtensionScriptInstanceDataPtr p_instance, GDExtensionConstStringNamePtr p_name)
{
    LeanCLRScriptInstance* instance = as_instance(p_instance);
    const StringName& name = *reinterpret_cast<const StringName*>(p_name);
    String managed_name = managed_virtual_name(name);
    if (!managed_name.is_empty())
    {
        return LeanCLRRuntimeBridge::has_script_method(instance->managed_object, managed_name, managed_virtual_argument_count(name));
    }

    return LeanCLRRuntimeBridge::has_script_method(instance->managed_object, String(name), 0) ||
           LeanCLRRuntimeBridge::has_script_method(instance->managed_object, String(name), 1);
}

void script_instance_invoke_ready(LeanCLRScriptInstance* p_instance)
{
    if (p_instance->ready_invoked)
    {
        return;
    }

    p_instance->ready_invoked = true;
    LeanCLRRuntimeBridge::invoke_script_ready(p_instance->managed_object);
}

GDExtensionInt script_instance_get_method_argument_count(GDExtensionScriptInstanceDataPtr p_instance, GDExtensionConstStringNamePtr p_name,
                                                         GDExtensionBool* r_is_valid)
{
    *r_is_valid = script_instance_has_method(p_instance, p_name);
    const StringName& name = *reinterpret_cast<const StringName*>(p_name);
    String managed_name = managed_virtual_name(name);
    if (!managed_name.is_empty())
    {
        return managed_virtual_argument_count(name);
    }

    return LeanCLRRuntimeBridge::has_script_method(as_instance(p_instance)->managed_object, String(name), 1) ? 1 : 0;
}

void script_instance_call(GDExtensionScriptInstanceDataPtr p_instance, GDExtensionConstStringNamePtr p_method,
                          const GDExtensionConstVariantPtr* p_args, GDExtensionInt p_argument_count, GDExtensionVariantPtr r_return,
                          GDExtensionCallError* r_error)
{
    const StringName& method = *reinterpret_cast<const StringName*>(p_method);
    LeanCLRScriptInstance* instance = as_instance(p_instance);
    if (is_editor_scene_context(instance->owner) && !instance->script->_is_tool() && String(method).begins_with("_"))
    {
        *reinterpret_cast<Variant*>(r_return) = Variant();
        r_error->error = GDEXTENSION_CALL_ERROR_INVALID_METHOD;
        return;
    }

    String managed_name = managed_virtual_name(method);
    if (managed_name.is_empty())
    {
        const String method_name = String(method);
        if (LeanCLRRuntimeBridge::has_script_method(instance->managed_object, method_name, static_cast<int32_t>(p_argument_count)) ||
            (p_argument_count > 1 && LeanCLRRuntimeBridge::has_script_method(instance->managed_object, method_name, 1)))
        {
            std::vector<Variant> arguments;
            arguments.reserve(static_cast<size_t>(p_argument_count));
            for (GDExtensionInt i = 0; i < p_argument_count; ++i)
            {
                arguments.push_back(*reinterpret_cast<const Variant*>(p_args[i]));
            }
            Variant return_value;
            LeanCLRRuntimeBridge::invoke_script_method(instance->managed_object, method_name, arguments.data(), static_cast<int32_t>(arguments.size()), &return_value);
            *reinterpret_cast<Variant*>(r_return) = return_value;
            r_error->error = GDEXTENSION_CALL_OK;
            return;
        }
        else
        {
            r_error->error = GDEXTENSION_CALL_ERROR_INVALID_METHOD;
        }
    }
    else
    {
        if (method == StringName("_ready") && p_argument_count == 0)
        {
            script_instance_invoke_ready(instance);
            r_error->error = GDEXTENSION_CALL_OK;
        }
        else
        {
            std::vector<Variant> arguments;
            arguments.reserve(static_cast<size_t>(p_argument_count));
            for (GDExtensionInt i = 0; i < p_argument_count; ++i)
            {
                arguments.push_back(*reinterpret_cast<const Variant*>(p_args[i]));
            }
            Variant return_value;
            LeanCLRRuntimeBridge::invoke_script_method(instance->managed_object, managed_name, arguments.data(), static_cast<int32_t>(arguments.size()), &return_value);
            *reinterpret_cast<Variant*>(r_return) = return_value;
            r_error->error = GDEXTENSION_CALL_OK;
            return;
        }
    }
    *reinterpret_cast<Variant*>(r_return) = Variant();
}

void script_instance_notification(GDExtensionScriptInstanceDataPtr p_instance, int32_t p_what, GDExtensionBool p_reversed)
{
    if (p_reversed)
    {
        return;
    }

    LeanCLRScriptInstance* instance = as_instance(p_instance);
    if (is_editor_scene_context(instance->owner) && !instance->script->_is_tool())
    {
        return;
    }

    if (p_what == Node::NOTIFICATION_READY)
    {
        script_instance_invoke_ready(instance);
    }
    else if (p_what == Node::NOTIFICATION_EXIT_TREE)
    {
        LeanCLRRuntimeBridge::invoke_script_method(instance->managed_object, "_ExitTree");
    }
}

void script_instance_to_string(GDExtensionScriptInstanceDataPtr p_instance, GDExtensionBool* r_is_valid, GDExtensionStringPtr r_out)
{
    LeanCLRScriptInstance* instance = as_instance(p_instance);
    *reinterpret_cast<String*>(r_out) = "<LeanCLRScriptInstance:" + instance->script->get_type_name() + ">";
    *r_is_valid = true;
}

GDExtensionObjectPtr script_instance_get_script(GDExtensionScriptInstanceDataPtr p_instance)
{
    LeanCLRScriptInstance* instance = as_instance(p_instance);
    return instance->script.ptr() != nullptr ? instance->script->_owner : nullptr;
}

GDExtensionBool script_instance_is_placeholder(GDExtensionScriptInstanceDataPtr p_instance)
{
    (void)p_instance;
    return false;
}

GDExtensionScriptLanguagePtr script_instance_get_language(GDExtensionScriptInstanceDataPtr p_instance)
{
    (void)p_instance;
    ScriptLanguage* language = LeanCLRScriptLanguage::get_singleton();
    return language != nullptr ? language->_owner : nullptr;
}

void script_instance_free(GDExtensionScriptInstanceDataPtr p_instance)
{
    LeanCLRScriptInstance* instance = as_instance(p_instance);
    LeanCLRRuntimeBridge::unregister_script_object(instance->owner, instance->managed_object);
    LeanCLRRuntimeBridge::release_script_object(instance->managed_object);
    delete instance;
}

const GDExtensionScriptInstanceInfo3& script_instance_info()
{
    static const GDExtensionScriptInstanceInfo3 info = {
        script_instance_set,
        script_instance_get,
        script_instance_get_property_list,
        script_instance_free_property_list,
        nullptr,
        nullptr,
        nullptr,
        script_instance_get_owner,
        script_instance_get_property_state,
        script_instance_get_method_list,
        script_instance_free_method_list,
        script_instance_get_property_type,
        nullptr,
        script_instance_has_method,
        script_instance_get_method_argument_count,
        script_instance_call,
        script_instance_notification,
        script_instance_to_string,
        nullptr,
        nullptr,
        script_instance_get_script,
        script_instance_is_placeholder,
        script_instance_set,
        script_instance_get,
        script_instance_get_language,
        script_instance_free,
    };
    return info;
}

} // namespace

void LeanCLRScript::_bind_methods()
{
    ClassDB::bind_method(D_METHOD("get_assembly_name"), &LeanCLRScript::get_assembly_name);
    ClassDB::bind_method(D_METHOD("get_type_name"), &LeanCLRScript::get_type_name);
    ClassDB::bind_method(D_METHOD("get_entry_point"), &LeanCLRScript::get_entry_point);
}

bool LeanCLRScript::_editor_can_reload_from_file()
{
    return true;
}

bool LeanCLRScript::_can_instantiate() const
{
    return valid;
}

Ref<Script> LeanCLRScript::_get_base_script() const
{
    return Ref<Script>();
}

StringName LeanCLRScript::_get_global_name() const
{
    return StringName(type_name);
}

bool LeanCLRScript::_inherits_script(const Ref<Script>& p_script) const
{
    return p_script.ptr() == this;
}

StringName LeanCLRScript::_get_instance_base_type() const
{
    return base_type;
}

void* LeanCLRScript::_instance_create(Object* p_for_object) const
{
    if (!valid || p_for_object == nullptr)
    {
        return nullptr;
    }

    void* managed_object = LeanCLRRuntimeBridge::create_script_object(assembly_name, type_name, p_for_object);
    if (managed_object == nullptr)
    {
        return nullptr;
    }

    LeanCLRScriptInstance* instance = new LeanCLRScriptInstance;
    instance->owner = p_for_object;
    instance->script = Ref<LeanCLRScript>(const_cast<LeanCLRScript*>(this));
    instance->managed_object = managed_object;
    LeanCLRRuntimeBridge::register_script_object(p_for_object, managed_object);

    void* script_instance = gdextension_interface::script_instance_create3(&script_instance_info(), instance);
    if (script_instance == nullptr)
    {
        LeanCLRRuntimeBridge::unregister_script_object(p_for_object, managed_object);
        LeanCLRRuntimeBridge::release_script_object(managed_object);
        delete instance;
    }
    return script_instance;
}

void* LeanCLRScript::_placeholder_instance_create(Object* p_for_object) const
{
    (void)p_for_object;
    return nullptr;
}

bool LeanCLRScript::_has_source_code() const
{
    return !source_code.is_empty();
}

String LeanCLRScript::_get_source_code() const
{
    return source_code;
}

void LeanCLRScript::_set_source_code(const String& p_code)
{
    source_code = p_code;
    parse_source();
}

Error LeanCLRScript::_reload(bool p_keep_state)
{
    (void)p_keep_state;
    parse_source();
    return valid ? OK : ERR_PARSE_ERROR;
}

StringName LeanCLRScript::_get_doc_class_name() const
{
    return StringName(type_name);
}

TypedArray<Dictionary> LeanCLRScript::_get_documentation() const
{
    return TypedArray<Dictionary>();
}

String LeanCLRScript::_get_class_icon_path() const
{
    return String();
}

bool LeanCLRScript::_has_method(const StringName& p_method) const
{
    return p_method == StringName("_ready") || p_method == StringName("_process");
}

bool LeanCLRScript::_has_static_method(const StringName& p_method) const
{
    (void)p_method;
    return false;
}

Dictionary LeanCLRScript::_get_method_info(const StringName& p_method) const
{
    Dictionary method;
    method["name"] = p_method;
    return method;
}

bool LeanCLRScript::_is_tool() const
{
    return false;
}

bool LeanCLRScript::_is_valid() const
{
    return valid;
}

bool LeanCLRScript::_is_abstract() const
{
    return false;
}

ScriptLanguage* LeanCLRScript::_get_language() const
{
    return LeanCLRScriptLanguage::get_singleton();
}

bool LeanCLRScript::_has_script_signal(const StringName& p_signal) const
{
    (void)p_signal;
    return false;
}

TypedArray<Dictionary> LeanCLRScript::_get_script_signal_list() const
{
    return TypedArray<Dictionary>();
}

bool LeanCLRScript::_has_property_default_value(const StringName& p_property) const
{
    (void)p_property;
    return false;
}

Variant LeanCLRScript::_get_property_default_value(const StringName& p_property) const
{
    (void)p_property;
    return Variant();
}

void LeanCLRScript::_update_exports()
{
}

TypedArray<Dictionary> LeanCLRScript::_get_script_method_list() const
{
    TypedArray<Dictionary> methods;
    Dictionary method;
    method["name"] = StringName("_ready");
    methods.push_back(method);
    Dictionary process_method;
    process_method["name"] = StringName("_process");
    methods.push_back(process_method);
    return methods;
}

TypedArray<Dictionary> LeanCLRScript::_get_script_property_list() const
{
    return TypedArray<Dictionary>();
}

int32_t LeanCLRScript::_get_member_line(const StringName& p_member) const
{
    (void)p_member;
    return -1;
}

Dictionary LeanCLRScript::_get_constants() const
{
    return Dictionary();
}

TypedArray<StringName> LeanCLRScript::_get_members() const
{
    return TypedArray<StringName>();
}

bool LeanCLRScript::_is_placeholder_fallback_enabled() const
{
    return false;
}

Variant LeanCLRScript::_get_rpc_config() const
{
    return Variant();
}

void LeanCLRScript::set_path_hint(const String& p_path)
{
    path_hint = p_path;
}

String LeanCLRScript::get_assembly_name() const
{
    return assembly_name;
}

String LeanCLRScript::get_type_name() const
{
    return type_name;
}

String LeanCLRScript::get_entry_point() const
{
    return entry_point;
}

void LeanCLRScript::parse_source()
{
    assembly_name = String();
    type_name = String();
    entry_point = String();
    base_type = "Node";

    const String extension = path_hint.get_extension().to_lower();
    if (extension == "cs")
    {
        assembly_name = "Game";
        String namespace_name;
        String class_name;

        PackedStringArray lines = source_code.split("\n");
        for (int64_t i = 0; i < lines.size(); ++i)
        {
            const String line = lines[i].strip_edges();
            if (line.begins_with("// @assembly "))
            {
                assembly_name = line.substr(12).strip_edges();
            }
            else if (line.begins_with("// @type "))
            {
                type_name = line.substr(9).strip_edges();
            }
            else if (line.begins_with("// @base "))
            {
                base_type = StringName(line.substr(9).strip_edges());
            }
            else if (namespace_name.is_empty() && line.begins_with("namespace "))
            {
                namespace_name = line.substr(10).strip_edges().trim_suffix(";").trim_suffix("{").strip_edges();
            }
            else if (class_name.is_empty() && (line.find(" class ") >= 0 || line.begins_with("class ")))
            {
                PackedStringArray tokens = line.replace(":", " : ").split(" ", false);
                for (int64_t token_index = 0; token_index + 1 < tokens.size(); ++token_index)
                {
                    if (tokens[token_index] == "class")
                    {
                        class_name = tokens[token_index + 1].get_slice("<", 0).strip_edges();
                        break;
                    }
                }
            }
        }

        if (type_name.is_empty())
        {
            if (class_name.is_empty() && !path_hint.is_empty())
            {
                class_name = path_hint.get_file().get_basename();
            }
            type_name = namespace_name.is_empty() ? class_name : namespace_name + "." + class_name;
        }

        valid = !assembly_name.is_empty() && !type_name.is_empty();
        return;
    }

    PackedStringArray lines = source_code.split("\n");
    for (int64_t i = 0; i < lines.size(); ++i)
    {
        PackedStringArray pair = lines[i].strip_edges().split("=", false, 1);
        if (pair.size() != 2)
        {
            continue;
        }

        const String key = pair[0].strip_edges().to_lower();
        const String value = pair[1].strip_edges();
        if (key == "assembly")
        {
            assembly_name = value;
        }
        else if (key == "type")
        {
            type_name = value;
        }
        else if (key == "base")
        {
            base_type = StringName(value);
        }
        else if (key == "entry")
        {
            entry_point = value;
        }
    }

    valid = !assembly_name.is_empty() && !type_name.is_empty();
    if (!valid && !path_hint.is_empty())
    {
        type_name = path_hint.get_file().get_basename();
    }
}

} // namespace godot
