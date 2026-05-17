#pragma once

#include <godot_cpp/classes/node.hpp>
#include <godot_cpp/classes/input_event.hpp>
#include <godot_cpp/variant/node_path.hpp>
#include <godot_cpp/variant/string.hpp>

namespace godot
{

class LeanCLRHotReloadHost : public Node
{
    GDCLASS(LeanCLRHotReloadHost, Node)

  public:
    ~LeanCLRHotReloadHost();
    void forward_input(const Ref<InputEvent>& p_event);
    void use_attached_script(const String& p_assembly_name);
    bool reload_assembly(const String& p_assembly_name, const String& p_type_name);

    void set_script_owner_path(const NodePath& p_script_owner_path);
    NodePath get_script_owner_path() const;
    void set_assembly_directory(const String& p_assembly_directory);
    String get_assembly_directory() const;
    String get_loaded_assembly_name() const;

  protected:
    static void _bind_methods();
    void _notification(int p_what);

  private:
    bool should_skip_runtime() const;
    Object* get_script_owner() const;
    void* get_attached_script_object() const;
    void* get_active_script_object() const;

    NodePath script_owner_path;
    void* managed_object = nullptr;
    String loaded_assembly_name;
};

} // namespace godot
