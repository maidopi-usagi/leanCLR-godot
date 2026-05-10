#include "leanclr_main_node.h"

#include "leanclr_runtime_bridge.h"

namespace godot
{

void LeanCLRMain::_bind_methods()
{
}

LeanCLRMain::~LeanCLRMain()
{
    LeanCLRRuntimeBridge::release_script_object(managed_object);
    managed_object = nullptr;
}

void LeanCLRMain::_notification(int p_what)
{
    if (p_what != NOTIFICATION_READY || ready_invoked)
    {
        return;
    }

    ready_invoked = true;
    ensure_managed_object();
    LeanCLRRuntimeBridge::invoke_script_ready(managed_object);
}

void LeanCLRMain::ensure_managed_object()
{
    if (managed_object != nullptr)
    {
        return;
    }

    managed_object = LeanCLRRuntimeBridge::create_script_object("Game", "Game.ClassDbMain", this);
}

} // namespace godot
