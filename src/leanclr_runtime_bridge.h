#pragma once

#include <godot_cpp/variant/string.hpp>

#include <vector>

namespace godot
{

class Object;
class InputEvent;
class Variant;

struct LeanCLRScriptPropertyInfo
{
    String name;
    int32_t type = 0;
    int32_t hint = 0;
    String hint_string;
    int32_t usage = 6;
};

class LeanCLRRuntimeBridge
{
  public:
    static void set_assembly_directory(const String& p_directory);
    static String get_assembly_directory();

    static bool initialize();
    static void shutdown();
    static bool is_initialized();

    static bool load_assembly(const String& p_assembly_name);
    static bool invoke_static_entry(const String& p_assembly_name, const String& p_entry_point);
    static void* create_script_object(const String& p_assembly_name, const String& p_type_name, Object* p_owner = nullptr);
    static void release_script_object(void* p_managed_object);
    static bool has_script_method(void* p_managed_object, const String& p_method, int32_t p_argument_count);
    static bool invoke_script_method(void* p_managed_object, const String& p_method);
    static bool invoke_script_method(void* p_managed_object, const String& p_method, float p_argument);
    static bool invoke_script_method(void* p_managed_object, const String& p_method, double p_argument);
    static bool invoke_script_method(void* p_managed_object, const String& p_method, const Variant& p_argument);
    static bool invoke_script_method(void* p_managed_object, const String& p_method, const Variant* p_arguments, int32_t p_argument_count);
    static bool invoke_script_method(void* p_managed_object, const String& p_method, const Variant* p_arguments, int32_t p_argument_count, Variant* r_return);
    static bool invoke_script_method(void* p_managed_object, const String& p_method, InputEvent* p_argument);
    static bool get_script_property(void* p_managed_object, const String& p_property, Variant* r_value);
    static bool set_script_property(void* p_managed_object, const String& p_property, const Variant& p_value);
    static bool get_script_property_list(void* p_managed_object, std::vector<LeanCLRScriptPropertyInfo>& r_properties);
    static int32_t get_script_property_type(void* p_managed_object, const String& p_property, bool* r_is_valid);
    static bool invoke_script_ready(void* p_managed_object);
    static bool invoke_script_process(void* p_managed_object, double p_delta);
    static void register_script_object(Object* p_owner, void* p_managed_object);
    static void unregister_script_object(Object* p_owner, void* p_managed_object);
    static void* get_script_object_for_owner(Object* p_owner);
    static int32_t migrate_script_state(void* p_source_object, void* p_target_object);
    static String get_last_error();

};

} // namespace godot
