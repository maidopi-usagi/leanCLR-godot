#pragma once

#include <godot_cpp/core/class_db.hpp>

namespace godot
{

void initialize_leanclr_godot_module(ModuleInitializationLevel p_level);
void uninitialize_leanclr_godot_module(ModuleInitializationLevel p_level);

} // namespace godot
