#pragma once

#include <godot_cpp/classes/node.hpp>

namespace godot
{

class LeanCLRMain : public Node
{
    GDCLASS(LeanCLRMain, Node)

  public:
    LeanCLRMain() = default;
    ~LeanCLRMain();

  protected:
    static void _bind_methods();
    void _notification(int p_what);

  private:
    void ensure_managed_object();

    void* managed_object = nullptr;
    bool ready_invoked = false;
};

} // namespace godot
