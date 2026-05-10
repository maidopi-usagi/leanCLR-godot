#pragma once

#include <godot_cpp/classes/node.hpp>
#include <godot_cpp/classes/input_event.hpp>
#include <godot_cpp/variant/string.hpp>

namespace godot
{

class LeanCLRHotReloadHost : public Node
{
    GDCLASS(LeanCLRHotReloadHost, Node)

  public:
    ~LeanCLRHotReloadHost();
    void forward_input(const Ref<InputEvent>& p_event);

  protected:
    static void _bind_methods();
    void _notification(int p_what);

  private:
    void check_reload_marker();
    void reload_managed_object(const String& p_assembly_name);

    void* managed_object = nullptr;
    String loaded_assembly_name;
    double elapsed = 0.0;
};

} // namespace godot
