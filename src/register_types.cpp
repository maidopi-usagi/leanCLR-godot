#include "register_types.h"

#include "leanclr_runtime_bridge.h"
#include "leanclr_main_node.h"
#include "leanclr_hot_reload_host.h"
#include "leanclr_script.h"
#include "leanclr_script_language.h"
#include "leanclr_script_loader.h"
#include "leanclr_script_saver.h"

#include <gdextension_interface.h>
#include <godot_cpp/classes/resource_loader.hpp>
#include <godot_cpp/classes/resource_saver.hpp>
#include <godot_cpp/core/defs.hpp>
#include <godot_cpp/core/memory.hpp>
#include <godot_cpp/godot.hpp>

namespace godot
{

namespace
{

Ref<LeanCLRScriptLoader>* script_loader = nullptr;
Ref<LeanCLRScriptSaver>* script_saver = nullptr;

} // namespace

void initialize_leanclr_godot_module(ModuleInitializationLevel p_level)
{
    if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE)
    {
        return;
    }

    GDREGISTER_CLASS(LeanCLRScript);
    GDREGISTER_CLASS(LeanCLRScriptLanguage);
    GDREGISTER_CLASS(LeanCLRScriptLoader);
    GDREGISTER_CLASS(LeanCLRScriptSaver);
    GDREGISTER_CLASS(LeanCLRMain);
    GDREGISTER_CLASS(LeanCLRHotReloadHost);

    LeanCLRScriptLanguage::init_singleton();

    script_loader = memnew(Ref<LeanCLRScriptLoader>);
    script_loader->instantiate();
    ResourceLoader::get_singleton()->add_resource_format_loader(*script_loader, true);

    script_saver = memnew(Ref<LeanCLRScriptSaver>);
    script_saver->instantiate();
    ResourceSaver::get_singleton()->add_resource_format_saver(*script_saver, true);
}

void uninitialize_leanclr_godot_module(ModuleInitializationLevel p_level)
{
    if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE)
    {
        return;
    }

    if (script_saver != nullptr && script_saver->is_valid())
    {
        ResourceSaver::get_singleton()->remove_resource_format_saver(*script_saver);
        script_saver->unref();
        memdelete(script_saver);
        script_saver = nullptr;
    }

    if (script_loader != nullptr && script_loader->is_valid())
    {
        ResourceLoader::get_singleton()->remove_resource_format_loader(*script_loader);
        script_loader->unref();
        memdelete(script_loader);
        script_loader = nullptr;
    }

    LeanCLRScriptLanguage::deinit_singleton();
    LeanCLRRuntimeBridge::shutdown();
}

} // namespace godot

extern "C"
{

GDExtensionBool GDE_EXPORT leanclr_godot_library_init(GDExtensionInterfaceGetProcAddress p_get_proc_address,
                                                      GDExtensionClassLibraryPtr p_library,
                                                      GDExtensionInitialization* r_initialization)
{
    godot::GDExtensionBinding::InitObject init_obj(p_get_proc_address, p_library, r_initialization);
    init_obj.register_initializer(godot::initialize_leanclr_godot_module);
    init_obj.register_terminator(godot::uninitialize_leanclr_godot_module);
    init_obj.set_minimum_library_initialization_level(godot::MODULE_INITIALIZATION_LEVEL_SCENE);
    return init_obj.init();
}
}
