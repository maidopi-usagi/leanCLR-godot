#include "leanclr_runtime_bridge.h"

#include "generated/godot_api.generated.h"

#include <godot_cpp/classes/file_access.hpp>
#include <godot_cpp/classes/input_event.hpp>
#include <godot_cpp/variant/utility_functions.hpp>
#include <godot_cpp/variant/callable.hpp>
#include <godot_cpp/variant/callable_custom.hpp>
#include <godot_cpp/variant/char_string.hpp>
#include <godot_cpp/variant/packed_byte_array.hpp>
#include <godot_cpp/variant/variant.hpp>

#include "alloc/general_allocation.h"
#include "metadata/module_def.h"
#include "vm/assembly.h"
#include "vm/class.h"
#include "vm/customattribute.h"
#include "vm/field.h"
#include "vm/internal_calls.h"
#include "vm/method.h"
#include "vm/object.h"
#include "vm/rt_array.h"
#include "vm/rt_string.h"
#include "vm/runtime.h"
#include "vm/settings.h"
#include "interp/eval_stack_op.h"

#include <string>
#include <vector>
#include <unordered_map>

namespace godot
{

leanclr::vm::RtObject* create_managed_godot_object(const String& p_managed_type, Object* p_native_object);

namespace
{

std::string& assembly_directory()
{
    static std::string* directory = new std::string("res://leanclr");
    return *directory;
}

std::string& last_error()
{
    static std::string* error = new std::string;
    return *error;
}

bool& initialized()
{
    static bool value = false;
    return value;
}

bool& godot_icalls_registered()
{
    static bool value = false;
    return value;
}

std::unordered_map<Object*, leanclr::vm::RtObject*>& script_objects_by_owner()
{
    static std::unordered_map<Object*, leanclr::vm::RtObject*>* objects = new std::unordered_map<Object*, leanclr::vm::RtObject*>;
    return *objects;
}

leanclr::RtResult<leanclr::vm::FileData> godot_file_loader(const char* p_assembly_name, const char* p_extension)
{
    const String path = LeanCLRRuntimeBridge::get_assembly_directory().path_join(String(p_assembly_name) + "." + p_extension);
    PackedByteArray bytes = FileAccess::get_file_as_bytes(path);
    if (bytes.is_empty())
    {
        return leanclr::RtErr::FileNotFound;
    }

    uint8_t* data = static_cast<uint8_t*>(leanclr::alloc::GeneralAllocation::malloc(static_cast<size_t>(bytes.size())));
    if (data == nullptr)
    {
        return leanclr::RtErr::OutOfMemory;
    }

    for (int64_t i = 0; i < bytes.size(); ++i)
    {
        data[i] = bytes[i];
    }

    return leanclr::vm::FileData{data, static_cast<size_t>(bytes.size())};
}

String rt_string_to_godot(const leanclr::vm::RtString* p_string)
{
    if (p_string == nullptr)
    {
        return String();
    }

    String result;
    for (int32_t i = 0; i < p_string->length; ++i)
    {
        result += String::chr(static_cast<char32_t>(*(&p_string->first_char + i)));
    }
    return result;
}

leanclr::RtResultVoid godot_gd_print(leanclr::vm::RtString* p_message) noexcept
{
    UtilityFunctions::print(rt_string_to_godot(p_message));
    return leanclr::core::Unit{};
}

leanclr::RtResultVoid godot_gd_print_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,
                                              const leanclr::metadata::RtMethodInfo* p_method,
                                              const leanclr::interp::RtStackObject* p_params,
                                              leanclr::interp::RtStackObject* p_ret) noexcept
{
    (void)p_method_ptr;
    (void)p_method;
    (void)p_ret;
    leanclr::vm::RtString* message = leanclr::interp::EvalStackOp::get_param<leanclr::vm::RtString*>(p_params, 0);
    return godot_gd_print(message);
}


struct ManagedVector2
{
    float x;
    float y;
};

struct ManagedVector2i
{
    int32_t x;
    int32_t y;
};

struct ManagedVector3
{
    float x;
    float y;
    float z;
};

struct ManagedVector3i
{
    int32_t x;
    int32_t y;
    int32_t z;
};

struct ManagedVector4
{
    float x;
    float y;
    float z;
    float w;
};

struct ManagedVector4i
{
    int32_t x;
    int32_t y;
    int32_t z;
    int32_t w;
};

struct ManagedColor
{
    float r;
    float g;
    float b;
    float a;
};

struct ManagedRect2
{
    ManagedVector2 position;
    ManagedVector2 size;
};

struct ManagedRect2i
{
    ManagedVector2i position;
    ManagedVector2i size;
};

struct ManagedTransform2D
{
    ManagedVector2 x;
    ManagedVector2 y;
    ManagedVector2 origin;
};

struct ManagedAabb
{
    ManagedVector3 position;
    ManagedVector3 size;
};

struct ManagedQuaternion
{
    float x;
    float y;
    float z;
    float w;
};

struct ManagedBasis
{
    ManagedVector3 x;
    ManagedVector3 y;
    ManagedVector3 z;
};

struct ManagedTransform3D
{
    ManagedBasis basis;
    ManagedVector3 origin;
};

struct ManagedPlane
{
    ManagedVector3 normal;
    float d;
};

struct ManagedProjection
{
    ManagedVector4 x;
    ManagedVector4 y;
    ManagedVector4 z;
    ManagedVector4 w;
};

struct ManagedVariant
{
    int32_t type = 0;
    int32_t flags = 0;
    union
    {
        bool bool_value;
        int64_t int_value;
        double float_value;
        leanclr::vm::RtString* string_value;
        intptr_t native_ptr;
        ManagedVector2 vector2_value;
        ManagedVector2i vector2i_value;
        ManagedVector3 vector3_value;
        ManagedVector3i vector3i_value;
        ManagedVector4 vector4_value;
        ManagedVector4i vector4i_value;
        ManagedColor color_value;
        ManagedRect2 rect2_value;
        ManagedRect2i rect2i_value;
        ManagedTransform2D transform2d_value;
        ManagedAabb aabb_value;
        ManagedQuaternion quaternion_value;
        ManagedBasis basis_value;
        ManagedTransform3D transform3d_value;
        ManagedPlane plane_value;
        ManagedProjection projection_value;
        uint8_t storage[64];
    };
};

leanclr::metadata::RtModuleDef* load_module(const String& p_assembly_name);
leanclr::metadata::RtClass* find_class(leanclr::metadata::RtModuleDef* p_module, const String& p_type_name);

leanclr::vm::RtString* to_rt_string(const String& p_string)
{
    const CharString utf8 = p_string.utf8();
    return leanclr::vm::String::create_string_from_utf8cstr(utf8.get_data());
}

ManagedVariant to_managed_variant(const Variant& p_variant)
{
    ManagedVariant result;
    switch (p_variant.get_type())
    {
        case Variant::BOOL:
            result.type = 1;
            result.bool_value = static_cast<bool>(p_variant);
            break;
        case Variant::INT:
            result.type = 2;
            result.int_value = static_cast<int64_t>(p_variant);
            break;
        case Variant::FLOAT:
            result.type = 3;
            result.float_value = static_cast<double>(p_variant);
            break;
        case Variant::STRING:
            result.type = 4;
            result.string_value = to_rt_string(static_cast<String>(p_variant));
            break;
        case Variant::VECTOR2:
        {
            const Vector2 value = static_cast<Vector2>(p_variant);
            result.type = 5;
            result.vector2_value = {value.x, value.y};
            break;
        }
        case Variant::VECTOR2I:
        {
            const Vector2i value = static_cast<Vector2i>(p_variant);
            result.type = 6;
            result.vector2i_value = {value.x, value.y};
            break;
        }
        case Variant::RECT2:
        {
            const Rect2 value = static_cast<Rect2>(p_variant);
            result.type = 7;
            result.rect2_value = {{value.position.x, value.position.y}, {value.size.x, value.size.y}};
            break;
        }
        case Variant::RECT2I:
        {
            const Rect2i value = static_cast<Rect2i>(p_variant);
            result.type = 8;
            result.rect2i_value = {{value.position.x, value.position.y}, {value.size.x, value.size.y}};
            break;
        }
        case Variant::VECTOR3:
        {
            const Vector3 value = static_cast<Vector3>(p_variant);
            result.type = 9;
            result.vector3_value = {value.x, value.y, value.z};
            break;
        }
        case Variant::VECTOR3I:
        {
            const Vector3i value = static_cast<Vector3i>(p_variant);
            result.type = 10;
            result.vector3i_value = {value.x, value.y, value.z};
            break;
        }
        case Variant::TRANSFORM2D:
        {
            const Transform2D value = static_cast<Transform2D>(p_variant);
            result.type = 11;
            result.transform2d_value = {{value.columns[0].x, value.columns[0].y}, {value.columns[1].x, value.columns[1].y}, {value.columns[2].x, value.columns[2].y}};
            break;
        }
        case Variant::VECTOR4:
        {
            const Vector4 value = static_cast<Vector4>(p_variant);
            result.type = 12;
            result.vector4_value = {value.x, value.y, value.z, value.w};
            break;
        }
        case Variant::VECTOR4I:
        {
            const Vector4i value = static_cast<Vector4i>(p_variant);
            result.type = 13;
            result.vector4i_value = {value.x, value.y, value.z, value.w};
            break;
        }
        case Variant::QUATERNION:
        {
            const Quaternion value = static_cast<Quaternion>(p_variant);
            result.type = 15;
            result.quaternion_value = {value.x, value.y, value.z, value.w};
            break;
        }
        case Variant::AABB:
        {
            const AABB value = static_cast<AABB>(p_variant);
            result.type = 16;
            result.aabb_value = {{value.position.x, value.position.y, value.position.z}, {value.size.x, value.size.y, value.size.z}};
            break;
        }
        case Variant::BASIS:
        {
            const Basis value = static_cast<Basis>(p_variant);
            result.type = 17;
            result.basis_value = {{value.rows[0].x, value.rows[0].y, value.rows[0].z}, {value.rows[1].x, value.rows[1].y, value.rows[1].z}, {value.rows[2].x, value.rows[2].y, value.rows[2].z}};
            break;
        }
        case Variant::TRANSFORM3D:
        {
            const Transform3D value = static_cast<Transform3D>(p_variant);
            result.type = 18;
            result.transform3d_value = {{{value.basis.rows[0].x, value.basis.rows[0].y, value.basis.rows[0].z}, {value.basis.rows[1].x, value.basis.rows[1].y, value.basis.rows[1].z}, {value.basis.rows[2].x, value.basis.rows[2].y, value.basis.rows[2].z}}, {value.origin.x, value.origin.y, value.origin.z}};
            break;
        }
        case Variant::COLOR:
        {
            const Color value = static_cast<Color>(p_variant);
            result.type = 20;
            result.color_value = {value.r, value.g, value.b, value.a};
            break;
        }
        case Variant::STRING_NAME:
            result.type = 21;
            result.string_value = to_rt_string(String(static_cast<StringName>(p_variant)));
            break;
        case Variant::NODE_PATH:
            result.type = 22;
            result.string_value = to_rt_string(String(static_cast<NodePath>(p_variant)));
            break;
        case Variant::RID:
            result.type = 23;
            result.int_value = static_cast<RID>(p_variant).get_id();
            break;
        case Variant::OBJECT:
            result.type = 24;
            result.native_ptr = reinterpret_cast<intptr_t>(static_cast<Object*>(p_variant));
            break;
        default:
            result.type = 0;
            result.int_value = 0;
            break;
    }
    return result;
}

String managed_type_name(const leanclr::metadata::RtClass* p_class)
{
    if (p_class == nullptr)
    {
        return String();
    }
    String result;
    if (p_class->namespaze != nullptr && std::strlen(p_class->namespaze) > 0)
    {
        result = String(p_class->namespaze) + ".";
    }
    result += String(p_class->name != nullptr ? p_class->name : "");
    return result;
}

bool is_managed_type(const leanclr::metadata::RtTypeSig* p_type, const char* p_namespace, const char* p_name)
{
    if (p_type == nullptr || (p_type->ele_type != leanclr::metadata::RtElementType::Class && p_type->ele_type != leanclr::metadata::RtElementType::ValueType))
    {
        return false;
    }
    auto class_result = leanclr::vm::Class::get_class_from_typesig(p_type);
    if (class_result.is_err())
    {
        return false;
    }
    const leanclr::metadata::RtClass* klass = class_result.unwrap();
    return std::strcmp(klass->namespaze != nullptr ? klass->namespaze : "", p_namespace) == 0 &&
           std::strcmp(klass->name != nullptr ? klass->name : "", p_name) == 0;
}

bool is_godot_object_type(const leanclr::metadata::RtTypeSig* p_type)
{
    if (p_type == nullptr || p_type->ele_type != leanclr::metadata::RtElementType::Class)
    {
        return false;
    }
    auto class_result = leanclr::vm::Class::get_class_from_typesig(p_type);
    if (class_result.is_err())
    {
        return false;
    }
    const leanclr::metadata::RtClass* klass = class_result.unwrap();
    for (const leanclr::metadata::RtClass* current = klass; current != nullptr; current = current->parent)
    {
        if (std::strcmp(current->namespaze != nullptr ? current->namespaze : "", "Godot") == 0 &&
            std::strcmp(current->name != nullptr ? current->name : "", "GodotObject") == 0)
        {
            return true;
        }
    }
    return false;
}

bool is_hot_reload_field_type_supported(const leanclr::metadata::RtTypeSig* p_type)
{
    if (p_type == nullptr || p_type->by_ref)
    {
        return false;
    }

    using leanclr::metadata::RtElementType;
    switch (p_type->ele_type)
    {
        case RtElementType::Boolean:
        case RtElementType::Char:
        case RtElementType::I1:
        case RtElementType::U1:
        case RtElementType::I2:
        case RtElementType::U2:
        case RtElementType::I4:
        case RtElementType::U4:
        case RtElementType::I8:
        case RtElementType::U8:
        case RtElementType::R4:
        case RtElementType::R8:
        case RtElementType::I:
        case RtElementType::U:
        case RtElementType::String:
        case RtElementType::Object:
            return true;
        case RtElementType::ValueType:
            return true;
        case RtElementType::Class:
            return is_godot_object_type(p_type);
        default:
            return false;
    }
}

bool are_hot_reload_field_types_compatible(const leanclr::metadata::RtTypeSig* p_source, const leanclr::metadata::RtTypeSig* p_target)
{
    if (!is_hot_reload_field_type_supported(p_source) || !is_hot_reload_field_type_supported(p_target) || p_source->ele_type != p_target->ele_type)
    {
        return false;
    }

    using leanclr::metadata::RtElementType;
    if (p_source->ele_type == RtElementType::Class || p_source->ele_type == RtElementType::ValueType)
    {
        auto source_class = leanclr::vm::Class::get_class_from_typesig(p_source);
        auto target_class = leanclr::vm::Class::get_class_from_typesig(p_target);
        if (source_class.is_err() || target_class.is_err())
        {
            return false;
        }
        const leanclr::metadata::RtClass* source = source_class.unwrap();
        const leanclr::metadata::RtClass* target = target_class.unwrap();
        return std::strcmp(source->namespaze != nullptr ? source->namespaze : "", target->namespaze != nullptr ? target->namespaze : "") == 0 &&
               std::strcmp(source->name != nullptr ? source->name : "", target->name != nullptr ? target->name : "") == 0;
    }

    return true;
}

const leanclr::metadata::RtFieldInfo* find_migratable_field_by_name(const leanclr::metadata::RtClass* p_class, const char* p_name)
{
    if (p_class == nullptr || p_name == nullptr)
    {
        return nullptr;
    }

    for (uint16_t i = 0; i < p_class->field_count; ++i)
    {
        const leanclr::metadata::RtFieldInfo* field = p_class->fields + i;
        if (std::strcmp(field->name, p_name) == 0 && leanclr::vm::Field::is_instance(field) && !leanclr::vm::Field::is_static_included_literal_and_rva(field))
        {
            return field;
        }
    }
    return nullptr;
}

bool is_variant_array_method(const leanclr::metadata::RtMethodInfo* p_method)
{
    if (p_method == nullptr || p_method->parameter_count != 1)
    {
        return false;
    }
    const leanclr::metadata::RtTypeSig* parameter = p_method->parameters[0];
    return parameter != nullptr && parameter->ele_type == leanclr::metadata::RtElementType::SZArray &&
           is_managed_type(parameter->data.element_type, "Godot", "Variant");
}

bool can_convert_variant_to_parameter(const Variant& p_argument, const leanclr::metadata::RtTypeSig* p_parameter)
{
    using leanclr::metadata::RtElementType;
    if (p_parameter == nullptr || p_parameter->by_ref)
    {
        return false;
    }

    switch (p_parameter->ele_type)
    {
        case RtElementType::Boolean:
            return p_argument.get_type() == Variant::BOOL;
        case RtElementType::I1:
        case RtElementType::U1:
        case RtElementType::I2:
        case RtElementType::U2:
        case RtElementType::I4:
        case RtElementType::U4:
        case RtElementType::I8:
        case RtElementType::U8:
        case RtElementType::I:
        case RtElementType::U:
            return p_argument.get_type() == Variant::INT;
        case RtElementType::R4:
        case RtElementType::R8:
            return p_argument.get_type() == Variant::FLOAT || p_argument.get_type() == Variant::INT;
        case RtElementType::String:
            return p_argument.get_type() == Variant::STRING || p_argument.get_type() == Variant::STRING_NAME || p_argument.get_type() == Variant::NODE_PATH;
        case RtElementType::ValueType:
            if (is_managed_type(p_parameter, "Godot", "Variant"))
            {
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "StringName"))
            {
                return p_argument.get_type() == Variant::STRING_NAME || p_argument.get_type() == Variant::STRING;
            }
            if (is_managed_type(p_parameter, "Godot", "NodePath"))
            {
                return p_argument.get_type() == Variant::NODE_PATH || p_argument.get_type() == Variant::STRING;
            }
            if (is_managed_type(p_parameter, "Godot", "RID"))
            {
                return p_argument.get_type() == Variant::RID;
            }
            if (is_managed_type(p_parameter, "Godot", "Vector2"))
            {
                return p_argument.get_type() == Variant::VECTOR2;
            }
            if (is_managed_type(p_parameter, "Godot", "Vector2i"))
            {
                return p_argument.get_type() == Variant::VECTOR2I;
            }
            if (is_managed_type(p_parameter, "Godot", "Vector3"))
            {
                return p_argument.get_type() == Variant::VECTOR3;
            }
            if (is_managed_type(p_parameter, "Godot", "Vector3i"))
            {
                return p_argument.get_type() == Variant::VECTOR3I;
            }
            if (is_managed_type(p_parameter, "Godot", "Vector4"))
            {
                return p_argument.get_type() == Variant::VECTOR4;
            }
            if (is_managed_type(p_parameter, "Godot", "Vector4i"))
            {
                return p_argument.get_type() == Variant::VECTOR4I;
            }
            if (is_managed_type(p_parameter, "Godot", "Color"))
            {
                return p_argument.get_type() == Variant::COLOR;
            }
            if (is_managed_type(p_parameter, "Godot", "Rect2"))
            {
                return p_argument.get_type() == Variant::RECT2;
            }
            if (is_managed_type(p_parameter, "Godot", "Rect2i"))
            {
                return p_argument.get_type() == Variant::RECT2I;
            }
            if (is_managed_type(p_parameter, "Godot", "Transform2D"))
            {
                return p_argument.get_type() == Variant::TRANSFORM2D;
            }
            if (is_managed_type(p_parameter, "Godot", "Aabb"))
            {
                return p_argument.get_type() == Variant::AABB;
            }
            if (is_managed_type(p_parameter, "Godot", "Quaternion"))
            {
                return p_argument.get_type() == Variant::QUATERNION;
            }
            if (is_managed_type(p_parameter, "Godot", "Basis"))
            {
                return p_argument.get_type() == Variant::BASIS;
            }
            if (is_managed_type(p_parameter, "Godot", "Transform3D"))
            {
                return p_argument.get_type() == Variant::TRANSFORM3D;
            }
            return false;
        case RtElementType::Class:
            if (is_godot_object_type(p_parameter))
            {
                return p_argument.get_type() == Variant::OBJECT || p_argument.get_type() == Variant::NIL;
            }
            return false;
        default:
            return false;
    }
}


Variant::Type managed_type_to_variant_type(const leanclr::metadata::RtTypeSig* p_type)
{
    using leanclr::metadata::RtElementType;
    if (p_type == nullptr)
    {
        return Variant::NIL;
    }
    switch (p_type->ele_type)
    {
        case RtElementType::Boolean:
            return Variant::BOOL;
        case RtElementType::I1:
        case RtElementType::U1:
        case RtElementType::I2:
        case RtElementType::U2:
        case RtElementType::I4:
        case RtElementType::U4:
        case RtElementType::I8:
        case RtElementType::U8:
        case RtElementType::I:
        case RtElementType::U:
            return Variant::INT;
        case RtElementType::R4:
        case RtElementType::R8:
            return Variant::FLOAT;
        case RtElementType::String:
            return Variant::STRING;
        case RtElementType::ValueType:
            if (is_managed_type(p_type, "Godot", "Variant"))
            {
                return Variant::NIL;
            }
            if (is_managed_type(p_type, "Godot", "StringName"))
            {
                return Variant::STRING_NAME;
            }
            if (is_managed_type(p_type, "Godot", "NodePath"))
            {
                return Variant::NODE_PATH;
            }
            if (is_managed_type(p_type, "Godot", "RID"))
            {
                return Variant::RID;
            }
            if (is_managed_type(p_type, "Godot", "Vector2"))
            {
                return Variant::VECTOR2;
            }
            if (is_managed_type(p_type, "Godot", "Vector2i"))
            {
                return Variant::VECTOR2I;
            }
            if (is_managed_type(p_type, "Godot", "Vector3"))
            {
                return Variant::VECTOR3;
            }
            if (is_managed_type(p_type, "Godot", "Vector3i"))
            {
                return Variant::VECTOR3I;
            }
            if (is_managed_type(p_type, "Godot", "Vector4"))
            {
                return Variant::VECTOR4;
            }
            if (is_managed_type(p_type, "Godot", "Vector4i"))
            {
                return Variant::VECTOR4I;
            }
            if (is_managed_type(p_type, "Godot", "Color"))
            {
                return Variant::COLOR;
            }
            if (is_managed_type(p_type, "Godot", "Rect2"))
            {
                return Variant::RECT2;
            }
            if (is_managed_type(p_type, "Godot", "Rect2i"))
            {
                return Variant::RECT2I;
            }
            if (is_managed_type(p_type, "Godot", "Transform2D"))
            {
                return Variant::TRANSFORM2D;
            }
            if (is_managed_type(p_type, "Godot", "Aabb"))
            {
                return Variant::AABB;
            }
            if (is_managed_type(p_type, "Godot", "Quaternion"))
            {
                return Variant::QUATERNION;
            }
            if (is_managed_type(p_type, "Godot", "Basis"))
            {
                return Variant::BASIS;
            }
            if (is_managed_type(p_type, "Godot", "Transform3D"))
            {
                return Variant::TRANSFORM3D;
            }
            return Variant::NIL;
        case RtElementType::Class:
            return is_godot_object_type(p_type) ? Variant::OBJECT : Variant::NIL;
        default:
            return Variant::NIL;
    }
}

const leanclr::metadata::RtPropertyInfo* find_script_property(leanclr::vm::RtObject* p_object, const String& p_property)
{
    if (p_object == nullptr || p_object->klass == nullptr)
    {
        return nullptr;
    }
    const CharString property_name = p_property.utf8();
    return leanclr::vm::Class::get_property_for_name(p_object->klass, property_name.get_data(), true);
}


bool get_export_attribute_metadata(const leanclr::metadata::RtPropertyInfo* p_property, LeanCLRScriptPropertyInfo& r_info)
{
    if (p_property == nullptr || p_property->parent == nullptr || p_property->parent->image == nullptr)
    {
        return false;
    }

    leanclr::metadata::RtModuleDef* compat_module = load_module("GodotSharpCompat");
    if (compat_module == nullptr)
    {
        return false;
    }

    leanclr::metadata::RtClass* attr_class = find_class(compat_module, "Godot.ExportAttribute");
    if (attr_class == nullptr)
    {
        return false;
    }

    auto attrs_result = leanclr::vm::CustomAttribute::get_customattributes_on_target_token(p_property->parent->image, p_property->token, attr_class);
    if (attrs_result.is_err())
    {
        return false;
    }

    leanclr::vm::RtArray* attrs = attrs_result.unwrap();
    if (attrs == nullptr || leanclr::vm::Array::get_array_length(attrs) == 0)
    {
        return false;
    }

    leanclr::vm::RtObject* attr = leanclr::vm::Array::get_array_data_at<leanclr::vm::RtObject*>(attrs, 0);
    if (attr == nullptr || attr->klass == nullptr)
    {
        return false;
    }

    const leanclr::metadata::RtFieldInfo* hint_field = leanclr::vm::Class::get_field_for_name(attr->klass, "Hint", true);
    const leanclr::metadata::RtFieldInfo* hint_string_field = leanclr::vm::Class::get_field_for_name(attr->klass, "HintString", true);
    const leanclr::metadata::RtFieldInfo* usage_field = leanclr::vm::Class::get_field_for_name(attr->klass, "Usage", true);
    if (hint_field != nullptr)
    {
        int32_t hint = 0;
        if (!leanclr::vm::Field::get_instance_value(hint_field, attr, &hint).is_err())
        {
            r_info.hint = hint;
        }
    }
    if (hint_string_field != nullptr)
    {
        leanclr::vm::RtString* hint_string = nullptr;
        if (!leanclr::vm::Field::get_instance_value(hint_string_field, attr, &hint_string).is_err())
        {
            r_info.hint_string = rt_string_to_godot(hint_string);
        }
    }
    if (usage_field != nullptr)
    {
        int64_t usage = 6;
        if (!leanclr::vm::Field::get_instance_value(usage_field, attr, &usage).is_err())
        {
            r_info.usage = static_cast<int32_t>(usage);
        }
    }
    return true;
}

bool is_script_property_visible(const leanclr::metadata::RtPropertyInfo* p_property)
{
    return p_property != nullptr && p_property->get_method != nullptr && p_property->set_method != nullptr &&
           !leanclr::vm::Method::is_static(p_property->get_method) && !leanclr::vm::Method::is_static(p_property->set_method) &&
           leanclr::vm::Method::is_public(p_property->get_method) && leanclr::vm::Method::is_public(p_property->set_method) &&
           p_property->set_method->parameter_count == 1 && managed_type_to_variant_type(p_property->property_sig.type_sig) != Variant::NIL;
}

const leanclr::metadata::RtMethodInfo* find_compatible_script_method(leanclr::vm::RtObject* p_object, const String& p_method, const Variant* p_arguments,
                                                                    int32_t p_argument_count)
{
    if (p_object == nullptr)
    {
        return nullptr;
    }

    const CharString method_name = p_method.utf8();
    for (uint16_t i = 0; i < p_object->klass->method_count; ++i)
    {
        const leanclr::metadata::RtMethodInfo* method = p_object->klass->methods[i];
        if (std::strcmp(method->name, method_name.get_data()) != 0 || method->parameter_count != static_cast<uint16_t>(p_argument_count))
        {
            continue;
        }

        bool compatible = true;
        for (int32_t argument_index = 0; argument_index < p_argument_count; ++argument_index)
        {
            if (!can_convert_variant_to_parameter(p_arguments[argument_index], method->parameters[argument_index]))
            {
                compatible = false;
                break;
            }
        }
        if (compatible)
        {
            return method;
        }
    }

    if (p_argument_count > 1)
    {
        for (uint16_t i = 0; i < p_object->klass->method_count; ++i)
        {
            const leanclr::metadata::RtMethodInfo* method = p_object->klass->methods[i];
            if (std::strcmp(method->name, method_name.get_data()) == 0 && is_variant_array_method(method))
            {
                return method;
            }
        }
    }

    return nullptr;
}

struct ScriptArgumentStorage
{
    bool bool_value = false;
    int8_t i8_value = 0;
    uint8_t u8_value = 0;
    int16_t i16_value = 0;
    uint16_t u16_value = 0;
    int32_t i32_value = 0;
    uint32_t u32_value = 0;
    int64_t i64_value = 0;
    uint64_t u64_value = 0;
    float f32_value = 0.0f;
    double f64_value = 0.0;
    leanclr::vm::RtString* string_value = nullptr;
    leanclr::vm::RtObject* object_value = nullptr;
    ManagedVariant variant_value;
    ManagedVector2 vector2_value;
    ManagedVector2i vector2i_value;
    ManagedVector3 vector3_value;
    ManagedVector3i vector3i_value;
    ManagedVector4 vector4_value;
    ManagedVector4i vector4i_value;
    ManagedColor color_value;
    ManagedRect2 rect2_value;
    ManagedRect2i rect2i_value;
    ManagedTransform2D transform2d_value;
    ManagedAabb aabb_value;
    ManagedQuaternion quaternion_value;
    ManagedBasis basis_value;
    ManagedTransform3D transform3d_value;
    int64_t rid_value = 0;
    const void* pointer = nullptr;
};

bool fill_script_argument_storage(const Variant& p_argument, const leanclr::metadata::RtTypeSig* p_parameter, ScriptArgumentStorage& r_storage)
{
    using leanclr::metadata::RtElementType;
    switch (p_parameter->ele_type)
    {
        case RtElementType::Boolean:
            r_storage.bool_value = static_cast<bool>(p_argument);
            r_storage.pointer = &r_storage.bool_value;
            return true;
        case RtElementType::I1:
            r_storage.i8_value = static_cast<int8_t>(static_cast<int64_t>(p_argument));
            r_storage.pointer = &r_storage.i8_value;
            return true;
        case RtElementType::U1:
            r_storage.u8_value = static_cast<uint8_t>(static_cast<int64_t>(p_argument));
            r_storage.pointer = &r_storage.u8_value;
            return true;
        case RtElementType::I2:
            r_storage.i16_value = static_cast<int16_t>(static_cast<int64_t>(p_argument));
            r_storage.pointer = &r_storage.i16_value;
            return true;
        case RtElementType::U2:
            r_storage.u16_value = static_cast<uint16_t>(static_cast<int64_t>(p_argument));
            r_storage.pointer = &r_storage.u16_value;
            return true;
        case RtElementType::I4:
            r_storage.i32_value = static_cast<int32_t>(static_cast<int64_t>(p_argument));
            r_storage.pointer = &r_storage.i32_value;
            return true;
        case RtElementType::U4:
            r_storage.u32_value = static_cast<uint32_t>(static_cast<int64_t>(p_argument));
            r_storage.pointer = &r_storage.u32_value;
            return true;
        case RtElementType::I8:
        case RtElementType::I:
            r_storage.i64_value = static_cast<int64_t>(p_argument);
            r_storage.pointer = &r_storage.i64_value;
            return true;
        case RtElementType::U8:
        case RtElementType::U:
            r_storage.u64_value = static_cast<uint64_t>(static_cast<int64_t>(p_argument));
            r_storage.pointer = &r_storage.u64_value;
            return true;
        case RtElementType::R4:
            r_storage.f32_value = static_cast<float>(static_cast<double>(p_argument));
            r_storage.pointer = &r_storage.f32_value;
            return true;
        case RtElementType::R8:
            r_storage.f64_value = static_cast<double>(p_argument);
            r_storage.pointer = &r_storage.f64_value;
            return true;
        case RtElementType::String:
            r_storage.string_value = to_rt_string(String(p_argument));
            r_storage.pointer = r_storage.string_value;
            return true;
        case RtElementType::ValueType:
            if (is_managed_type(p_parameter, "Godot", "Variant"))
            {
                r_storage.variant_value = to_managed_variant(p_argument);
                r_storage.pointer = &r_storage.variant_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "StringName") || is_managed_type(p_parameter, "Godot", "NodePath"))
            {
                r_storage.string_value = to_rt_string(String(p_argument));
                r_storage.pointer = &r_storage.string_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "RID"))
            {
                r_storage.rid_value = static_cast<RID>(p_argument).get_id();
                r_storage.pointer = &r_storage.rid_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Vector2"))
            {
                const Vector2 value = static_cast<Vector2>(p_argument);
                r_storage.vector2_value = {value.x, value.y};
                r_storage.pointer = &r_storage.vector2_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Vector2i"))
            {
                const Vector2i value = static_cast<Vector2i>(p_argument);
                r_storage.vector2i_value = {value.x, value.y};
                r_storage.pointer = &r_storage.vector2i_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Vector3"))
            {
                const Vector3 value = static_cast<Vector3>(p_argument);
                r_storage.vector3_value = {value.x, value.y, value.z};
                r_storage.pointer = &r_storage.vector3_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Vector3i"))
            {
                const Vector3i value = static_cast<Vector3i>(p_argument);
                r_storage.vector3i_value = {value.x, value.y, value.z};
                r_storage.pointer = &r_storage.vector3i_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Vector4"))
            {
                const Vector4 value = static_cast<Vector4>(p_argument);
                r_storage.vector4_value = {value.x, value.y, value.z, value.w};
                r_storage.pointer = &r_storage.vector4_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Vector4i"))
            {
                const Vector4i value = static_cast<Vector4i>(p_argument);
                r_storage.vector4i_value = {value.x, value.y, value.z, value.w};
                r_storage.pointer = &r_storage.vector4i_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Color"))
            {
                const Color value = static_cast<Color>(p_argument);
                r_storage.color_value = {value.r, value.g, value.b, value.a};
                r_storage.pointer = &r_storage.color_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Rect2"))
            {
                const Rect2 value = static_cast<Rect2>(p_argument);
                r_storage.rect2_value = {{value.position.x, value.position.y}, {value.size.x, value.size.y}};
                r_storage.pointer = &r_storage.rect2_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Rect2i"))
            {
                const Rect2i value = static_cast<Rect2i>(p_argument);
                r_storage.rect2i_value = {{value.position.x, value.position.y}, {value.size.x, value.size.y}};
                r_storage.pointer = &r_storage.rect2i_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Transform2D"))
            {
                const Transform2D value = static_cast<Transform2D>(p_argument);
                r_storage.transform2d_value = {{value.columns[0].x, value.columns[0].y}, {value.columns[1].x, value.columns[1].y}, {value.columns[2].x, value.columns[2].y}};
                r_storage.pointer = &r_storage.transform2d_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Aabb"))
            {
                const AABB value = static_cast<AABB>(p_argument);
                r_storage.aabb_value = {{value.position.x, value.position.y, value.position.z}, {value.size.x, value.size.y, value.size.z}};
                r_storage.pointer = &r_storage.aabb_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Quaternion"))
            {
                const Quaternion value = static_cast<Quaternion>(p_argument);
                r_storage.quaternion_value = {value.x, value.y, value.z, value.w};
                r_storage.pointer = &r_storage.quaternion_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Basis"))
            {
                const Basis value = static_cast<Basis>(p_argument);
                r_storage.basis_value = {{value.rows[0].x, value.rows[0].y, value.rows[0].z}, {value.rows[1].x, value.rows[1].y, value.rows[1].z}, {value.rows[2].x, value.rows[2].y, value.rows[2].z}};
                r_storage.pointer = &r_storage.basis_value;
                return true;
            }
            if (is_managed_type(p_parameter, "Godot", "Transform3D"))
            {
                const Transform3D value = static_cast<Transform3D>(p_argument);
                r_storage.transform3d_value = {{{value.basis.rows[0].x, value.basis.rows[0].y, value.basis.rows[0].z}, {value.basis.rows[1].x, value.basis.rows[1].y, value.basis.rows[1].z}, {value.basis.rows[2].x, value.basis.rows[2].y, value.basis.rows[2].z}}, {value.origin.x, value.origin.y, value.origin.z}};
                r_storage.pointer = &r_storage.transform3d_value;
                return true;
            }
            return false;
        case RtElementType::Class:
            if (is_godot_object_type(p_parameter))
            {
                Object* native_object = p_argument.get_type() == Variant::NIL ? nullptr : static_cast<Object*>(p_argument);
                if (native_object == nullptr)
                {
                    r_storage.object_value = nullptr;
                }
                else
                {
                    auto class_result = leanclr::vm::Class::get_class_from_typesig(p_parameter);
                    if (class_result.is_err())
                    {
                        return false;
                    }
                    r_storage.object_value = create_managed_godot_object(managed_type_name(class_result.unwrap()), native_object);
                    if (r_storage.object_value == nullptr)
                    {
                        return false;
                    }
                }
                r_storage.pointer = r_storage.object_value;
                return true;
            }
            return false;
        default:
            return false;
    }
}

Variant managed_variant_to_godot(const ManagedVariant& p_variant)
{
    switch (p_variant.type)
    {
        case 1:
            return Variant(p_variant.bool_value);
        case 2:
            return Variant(p_variant.int_value);
        case 3:
            return Variant(p_variant.float_value);
        case 4:
            return Variant(rt_string_to_godot(p_variant.string_value));
        case 5:
            return Variant(Vector2(p_variant.vector2_value.x, p_variant.vector2_value.y));
        case 6:
            return Variant(Vector2i(p_variant.vector2i_value.x, p_variant.vector2i_value.y));
        case 7:
            return Variant(Rect2(Vector2(p_variant.rect2_value.position.x, p_variant.rect2_value.position.y), Vector2(p_variant.rect2_value.size.x, p_variant.rect2_value.size.y)));
        case 8:
            return Variant(Rect2i(Vector2i(p_variant.rect2i_value.position.x, p_variant.rect2i_value.position.y), Vector2i(p_variant.rect2i_value.size.x, p_variant.rect2i_value.size.y)));
        case 9:
            return Variant(Vector3(p_variant.vector3_value.x, p_variant.vector3_value.y, p_variant.vector3_value.z));
        case 10:
            return Variant(Vector3i(p_variant.vector3i_value.x, p_variant.vector3i_value.y, p_variant.vector3i_value.z));
        case 11:
            return Variant(Transform2D(Vector2(p_variant.transform2d_value.x.x, p_variant.transform2d_value.x.y), Vector2(p_variant.transform2d_value.y.x, p_variant.transform2d_value.y.y), Vector2(p_variant.transform2d_value.origin.x, p_variant.transform2d_value.origin.y)));
        case 12:
            return Variant(Vector4(p_variant.vector4_value.x, p_variant.vector4_value.y, p_variant.vector4_value.z, p_variant.vector4_value.w));
        case 13:
            return Variant(Vector4i(p_variant.vector4i_value.x, p_variant.vector4i_value.y, p_variant.vector4i_value.z, p_variant.vector4i_value.w));
        case 15:
            return Variant(Quaternion(p_variant.quaternion_value.x, p_variant.quaternion_value.y, p_variant.quaternion_value.z, p_variant.quaternion_value.w));
        case 16:
            return Variant(AABB(Vector3(p_variant.aabb_value.position.x, p_variant.aabb_value.position.y, p_variant.aabb_value.position.z), Vector3(p_variant.aabb_value.size.x, p_variant.aabb_value.size.y, p_variant.aabb_value.size.z)));
        case 17:
            return Variant(Basis(Vector3(p_variant.basis_value.x.x, p_variant.basis_value.x.y, p_variant.basis_value.x.z), Vector3(p_variant.basis_value.y.x, p_variant.basis_value.y.y, p_variant.basis_value.y.z), Vector3(p_variant.basis_value.z.x, p_variant.basis_value.z.y, p_variant.basis_value.z.z)));
        case 18:
            return Variant(Transform3D(Basis(Vector3(p_variant.transform3d_value.basis.x.x, p_variant.transform3d_value.basis.x.y, p_variant.transform3d_value.basis.x.z), Vector3(p_variant.transform3d_value.basis.y.x, p_variant.transform3d_value.basis.y.y, p_variant.transform3d_value.basis.y.z), Vector3(p_variant.transform3d_value.basis.z.x, p_variant.transform3d_value.basis.z.y, p_variant.transform3d_value.basis.z.z)), Vector3(p_variant.transform3d_value.origin.x, p_variant.transform3d_value.origin.y, p_variant.transform3d_value.origin.z)));
        case 20:
            return Variant(Color(p_variant.color_value.r, p_variant.color_value.g, p_variant.color_value.b, p_variant.color_value.a));
        case 21:
            return Variant(StringName(rt_string_to_godot(p_variant.string_value)));
        case 22:
            return Variant(NodePath(rt_string_to_godot(p_variant.string_value)));
        case 23:
            return Variant(RID());
        case 24:
            return Variant(reinterpret_cast<Object*>(p_variant.native_ptr));
        default:
            return Variant();
    }
}

Variant return_object_to_variant(const leanclr::metadata::RtTypeSig* p_return_type, leanclr::vm::RtObject* p_return_object)
{
    using leanclr::metadata::RtElementType;
    if (p_return_type == nullptr || p_return_type->is_void() || p_return_object == nullptr)
    {
        return Variant();
    }

    if (p_return_type->ele_type == RtElementType::String)
    {
        return Variant(rt_string_to_godot(reinterpret_cast<leanclr::vm::RtString*>(p_return_object)));
    }

    auto class_result = leanclr::vm::Class::get_class_from_typesig(p_return_type);
    if (class_result.is_err())
    {
        return Variant();
    }
    leanclr::metadata::RtClass* return_class = class_result.unwrap();

    switch (p_return_type->ele_type)
    {
        case RtElementType::Boolean:
        { bool value = false; leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false); return Variant(value); }
        case RtElementType::I1:
        { int8_t value = 0; leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false); return Variant(static_cast<int64_t>(value)); }
        case RtElementType::U1:
        { uint8_t value = 0; leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false); return Variant(static_cast<int64_t>(value)); }
        case RtElementType::I2:
        { int16_t value = 0; leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false); return Variant(static_cast<int64_t>(value)); }
        case RtElementType::U2:
        { uint16_t value = 0; leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false); return Variant(static_cast<int64_t>(value)); }
        case RtElementType::I4:
        { int32_t value = 0; leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false); return Variant(static_cast<int64_t>(value)); }
        case RtElementType::U4:
        { uint32_t value = 0; leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false); return Variant(static_cast<int64_t>(value)); }
        case RtElementType::I8:
        case RtElementType::I:
        { int64_t value = 0; leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false); return Variant(value); }
        case RtElementType::U8:
        case RtElementType::U:
        { uint64_t value = 0; leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false); return Variant(static_cast<int64_t>(value)); }
        case RtElementType::R4:
        { float value = 0.0f; leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false); return Variant(static_cast<double>(value)); }
        case RtElementType::R8:
        { double value = 0.0; leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false); return Variant(value); }
        case RtElementType::ValueType:
            if (is_managed_type(p_return_type, "Godot", "Variant"))
            {
                ManagedVariant value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return managed_variant_to_godot(value);
            }
            if (is_managed_type(p_return_type, "Godot", "StringName"))
            {
                leanclr::vm::RtString* value = nullptr;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(StringName(rt_string_to_godot(value)));
            }
            if (is_managed_type(p_return_type, "Godot", "NodePath"))
            {
                leanclr::vm::RtString* value = nullptr;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(NodePath(rt_string_to_godot(value)));
            }
            if (is_managed_type(p_return_type, "Godot", "RID"))
            {
                int64_t value = 0;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(RID());
            }
            if (is_managed_type(p_return_type, "Godot", "Vector2"))
            {
                ManagedVector2 value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Vector2(value.x, value.y));
            }
            if (is_managed_type(p_return_type, "Godot", "Vector2i"))
            {
                ManagedVector2i value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Vector2i(value.x, value.y));
            }
            if (is_managed_type(p_return_type, "Godot", "Vector3"))
            {
                ManagedVector3 value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Vector3(value.x, value.y, value.z));
            }
            if (is_managed_type(p_return_type, "Godot", "Vector3i"))
            {
                ManagedVector3i value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Vector3i(value.x, value.y, value.z));
            }
            if (is_managed_type(p_return_type, "Godot", "Vector4"))
            {
                ManagedVector4 value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Vector4(value.x, value.y, value.z, value.w));
            }
            if (is_managed_type(p_return_type, "Godot", "Vector4i"))
            {
                ManagedVector4i value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Vector4i(value.x, value.y, value.z, value.w));
            }
            if (is_managed_type(p_return_type, "Godot", "Color"))
            {
                ManagedColor value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Color(value.r, value.g, value.b, value.a));
            }
            if (is_managed_type(p_return_type, "Godot", "Rect2"))
            {
                ManagedRect2 value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Rect2(Vector2(value.position.x, value.position.y), Vector2(value.size.x, value.size.y)));
            }
            if (is_managed_type(p_return_type, "Godot", "Rect2i"))
            {
                ManagedRect2i value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Rect2i(Vector2i(value.position.x, value.position.y), Vector2i(value.size.x, value.size.y)));
            }
            if (is_managed_type(p_return_type, "Godot", "Transform2D"))
            {
                ManagedTransform2D value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Transform2D(Vector2(value.x.x, value.x.y), Vector2(value.y.x, value.y.y), Vector2(value.origin.x, value.origin.y)));
            }
            if (is_managed_type(p_return_type, "Godot", "Aabb"))
            {
                ManagedAabb value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(AABB(Vector3(value.position.x, value.position.y, value.position.z), Vector3(value.size.x, value.size.y, value.size.z)));
            }
            if (is_managed_type(p_return_type, "Godot", "Quaternion"))
            {
                ManagedQuaternion value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Quaternion(value.x, value.y, value.z, value.w));
            }
            if (is_managed_type(p_return_type, "Godot", "Basis"))
            {
                ManagedBasis value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Basis(Vector3(value.x.x, value.x.y, value.x.z), Vector3(value.y.x, value.y.y, value.y.z), Vector3(value.z.x, value.z.y, value.z.z)));
            }
            if (is_managed_type(p_return_type, "Godot", "Transform3D"))
            {
                ManagedTransform3D value;
                leanclr::vm::Object::unbox_any(p_return_object, return_class, &value, false);
                return Variant(Transform3D(Basis(Vector3(value.basis.x.x, value.basis.x.y, value.basis.x.z), Vector3(value.basis.y.x, value.basis.y.y, value.basis.y.z), Vector3(value.basis.z.x, value.basis.z.y, value.basis.z.z)), Vector3(value.origin.x, value.origin.y, value.origin.z)));
            }
            return Variant();
        case RtElementType::Class:
            if (is_godot_object_type(p_return_type))
            {
                const leanclr::metadata::RtFieldInfo* native_ptr_field = leanclr::vm::Class::get_field_for_name(p_return_object->klass, "NativePtr", true);
                intptr_t native_ptr = 0;
                if (native_ptr_field != nullptr)
                {
                    leanclr::vm::Field::get_instance_value(native_ptr_field, p_return_object, &native_ptr);
                }
                return Variant(reinterpret_cast<Object*>(native_ptr));
            }
            return Variant();
        default:
            return Variant();
    }
}

struct RuntimeOpaqueValue
{
    void* value = nullptr;
    void (*destroy)(void*) = nullptr;
};

void destroy_runtime_callable(void* p_value)
{
    delete reinterpret_cast<Callable*>(p_value);
}

intptr_t new_runtime_callable_opaque(const Callable& p_callable)
{
    RuntimeOpaqueValue* opaque = memnew(RuntimeOpaqueValue);
    opaque->value = new Callable(p_callable);
    opaque->destroy = &destroy_runtime_callable;
    return reinterpret_cast<intptr_t>(opaque);
}

Variant invoke_managed_delegate_callable(int64_t p_delegate_id, const Variant** p_arguments, int32_t p_argument_count)
{
    leanclr::metadata::RtModuleDef* module = load_module("GodotSharpCompat");
    if (module == nullptr)
    {
        return Variant();
    }

    leanclr::metadata::RtClass* registry_class = find_class(module, "Godot.CallableDelegateRegistry");
    if (registry_class == nullptr)
    {
        return Variant();
    }

    const leanclr::metadata::RtMethodInfo* invoke_method =
        leanclr::vm::Method::find_matched_method_in_class_by_name_and_param_count(registry_class, "Invoke", 2);
    if (invoke_method == nullptr)
    {
        last_error() = "Failed to find Godot.CallableDelegateRegistry.Invoke.";
        return Variant();
    }

    leanclr::metadata::RtClass* variant_class = find_class(module, "Godot.Variant");
    if (variant_class == nullptr)
    {
        return Variant();
    }

    auto array_result = leanclr::vm::Array::new_szarray_from_ele_klass(variant_class, p_argument_count);
    if (array_result.is_err())
    {
        last_error() = ("Failed to allocate LeanCLR delegate Variant[] with error " + String::num_int64(static_cast<int64_t>(array_result.unwrap_err()))).utf8().get_data();
        return Variant();
    }

    leanclr::vm::RtArray* arguments = array_result.unwrap();
    for (int32_t i = 0; i < p_argument_count; ++i)
    {
        leanclr::vm::Array::set_array_data_at<ManagedVariant>(arguments, i, to_managed_variant(*p_arguments[i]));
    }

    const void* params[] = {&p_delegate_id, arguments};
    auto invoke_result = leanclr::vm::Runtime::invoke_with_run_cctor(invoke_method, nullptr, params);
    if (invoke_result.is_err())
    {
        last_error() = ("Failed to invoke LeanCLR delegate callable with error " + String::num_int64(static_cast<int64_t>(invoke_result.unwrap_err()))).utf8().get_data();
        return Variant();
    }

    last_error().clear();
    return return_object_to_variant(invoke_method->return_type, invoke_result.unwrap());
}

class ManagedDelegateCallable : public CallableCustom
{
    int64_t delegate_id = 0;

  public:
    explicit ManagedDelegateCallable(int64_t p_delegate_id) : delegate_id(p_delegate_id)
    {
    }

    uint32_t hash() const override
    {
        return static_cast<uint32_t>(delegate_id) ^ static_cast<uint32_t>(delegate_id >> 32);
    }

    String get_as_text() const override
    {
        return "LeanCLRDelegateCallable:" + String::num_int64(delegate_id);
    }

    CompareEqualFunc get_compare_equal_func() const override
    {
        return nullptr;
    }

    CompareLessFunc get_compare_less_func() const override
    {
        return nullptr;
    }

    bool is_valid() const override
    {
        return delegate_id != 0;
    }

    ObjectID get_object() const override
    {
        return ObjectID();
    }

    void call(const Variant** p_arguments, int p_argcount, Variant& r_return_value, GDExtensionCallError& r_call_error) const override
    {
        r_return_value = invoke_managed_delegate_callable(delegate_id, p_arguments, p_argcount);
        r_call_error.error = GDEXTENSION_CALL_OK;
    }
};

intptr_t godot_callable_create_delegate(int64_t p_delegate_id) noexcept
{
    return new_runtime_callable_opaque(Callable(memnew(ManagedDelegateCallable(p_delegate_id))));
}

leanclr::RtResultVoid godot_callable_create_delegate_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,
                                                             const leanclr::metadata::RtMethodInfo* p_method,
                                                             const leanclr::interp::RtStackObject* p_params,
                                                             leanclr::interp::RtStackObject* p_ret) noexcept
{
    (void)p_method_ptr;
    (void)p_method;
    const int64_t delegate_id = leanclr::interp::EvalStackOp::get_param<int64_t>(p_params, 0);
    leanclr::interp::EvalStackOp::set_return(p_ret, godot_callable_create_delegate(delegate_id));
    return leanclr::core::Unit{};
}

bool invoke_script_method_with_method(leanclr::vm::RtObject* p_object, const String& p_method, const leanclr::metadata::RtMethodInfo* p_target_method,
                                      const Variant* p_arguments, int32_t p_argument_count, Variant* r_return)
{
    if (p_target_method == nullptr)
    {
        last_error().clear();
        return true;
    }

    if (is_variant_array_method(p_target_method) && p_argument_count > 1)
    {
        leanclr::metadata::RtModuleDef* module = load_module("GodotSharpCompat");
        if (module == nullptr)
        {
            return false;
        }
        leanclr::metadata::RtClass* variant_class = find_class(module, "Godot.Variant");
        if (variant_class == nullptr)
        {
            return false;
        }
        auto array_result = leanclr::vm::Array::new_szarray_from_ele_klass(variant_class, p_argument_count);
        if (array_result.is_err())
        {
            last_error() = ("Failed to allocate LeanCLR Variant[] with error " + String::num_int64(static_cast<int64_t>(array_result.unwrap_err()))).utf8().get_data();
            return false;
        }
        leanclr::vm::RtArray* arguments = array_result.unwrap();
        for (int32_t i = 0; i < p_argument_count; ++i)
        {
            leanclr::vm::Array::set_array_data_at<ManagedVariant>(arguments, i, to_managed_variant(p_arguments[i]));
        }
        const void* params[] = {arguments};
        auto invoke_result = leanclr::vm::Runtime::invoke_with_run_cctor(p_target_method, p_object, params);
        if (invoke_result.is_err())
        {
            last_error() = ("Failed to invoke LeanCLR " + p_method + " with error " + String::num_int64(static_cast<int64_t>(invoke_result.unwrap_err()))).utf8().get_data();
            return false;
        }
        if (r_return != nullptr)
        {
            *r_return = return_object_to_variant(p_target_method->return_type, invoke_result.unwrap());
        }
        last_error().clear();
        return true;
    }

    std::vector<ScriptArgumentStorage> storage(static_cast<size_t>(p_argument_count));
    std::vector<const void*> params(static_cast<size_t>(p_argument_count));
    for (int32_t i = 0; i < p_argument_count; ++i)
    {
        if (!fill_script_argument_storage(p_arguments[i], p_target_method->parameters[i], storage[static_cast<size_t>(i)]))
        {
            last_error() = ("Failed to convert Godot Variant argument for LeanCLR method " + p_method + ".").utf8().get_data();
            return false;
        }
        params[static_cast<size_t>(i)] = storage[static_cast<size_t>(i)].pointer;
    }

    auto invoke_result = leanclr::vm::Runtime::invoke_with_run_cctor(p_target_method, p_object, params.empty() ? nullptr : params.data());
    if (invoke_result.is_err())
    {
        last_error() = ("Failed to invoke LeanCLR " + p_method + " with error " + String::num_int64(static_cast<int64_t>(invoke_result.unwrap_err()))).utf8().get_data();
        return false;
    }
    if (r_return != nullptr)
    {
        *r_return = return_object_to_variant(p_target_method->return_type, invoke_result.unwrap());
    }
    last_error().clear();
    return true;
}

bool attach_native_owner(leanclr::vm::RtObject* p_object, Object* p_owner)
{
    if (p_owner == nullptr)
    {
        return true;
    }

    const leanclr::metadata::RtFieldInfo* native_ptr_field = leanclr::vm::Class::get_field_for_name(p_object->klass, "NativePtr", true);
    if (native_ptr_field == nullptr)
    {
        last_error() = "Failed to find GodotObject.NativePtr field.";
        return false;
    }

    const intptr_t native_ptr = reinterpret_cast<intptr_t>(p_owner);
    auto result = leanclr::vm::Field::set_instance_value(native_ptr_field, p_object, &native_ptr);
    if (result.is_err())
    {
        last_error() = "Failed to assign Godot native owner handle.";
        return false;
    }
    return true;
}

void register_godot_internal_calls()
{
    if (godot_icalls_registered())
    {
        return;
    }

    leanclr::vm::InternalCalls::register_internal_call("Godot.GD::PrintInternal(System.String)",
                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_gd_print),
                                                       godot_gd_print_invoker);
    leanclr::vm::InternalCalls::register_internal_call("Godot.NativeCalls::GodotCallableCreateDelegate(System.Int64)",
                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_callable_create_delegate),
                                                       godot_callable_create_delegate_invoker);
    register_generated_godot_api_icalls();
    godot_icalls_registered() = true;
}

leanclr::metadata::RtModuleDef* load_module(const String& p_assembly_name)
{
    const CharString assembly_name = p_assembly_name.utf8();
    auto assembly_result = leanclr::vm::Assembly::load_by_name(assembly_name.get_data());
    if (assembly_result.is_err())
    {
        last_error() = ("Failed to load LeanCLR assembly '" + p_assembly_name + "' with error " +
                        String::num_int64(static_cast<int64_t>(assembly_result.unwrap_err()))).utf8().get_data();
        return nullptr;
    }
    return assembly_result.unwrap()->mod;
}

leanclr::metadata::RtClass* find_class(leanclr::metadata::RtModuleDef* p_module, const String& p_type_name)
{
    const CharString type_name = p_type_name.utf8();
    auto class_result = p_module->get_class_by_nested_full_name(type_name.get_data(), false, true);
    if (class_result.is_err())
    {
        last_error() = ("Failed to find LeanCLR class '" + p_type_name + "' with error " +
                        String::num_int64(static_cast<int64_t>(class_result.unwrap_err()))).utf8().get_data();
        return nullptr;
    }
    return class_result.unwrap();
}

} // namespace

void LeanCLRRuntimeBridge::set_assembly_directory(const String& p_directory)
{
    const CharString directory = (p_directory.is_empty() ? String("res://leanclr") : p_directory).utf8();
    assembly_directory() = directory.get_data();
}

String LeanCLRRuntimeBridge::get_assembly_directory()
{
    return String(assembly_directory().c_str());
}

bool LeanCLRRuntimeBridge::initialize()
{
    if (initialized())
    {
        return true;
    }

    leanclr::vm::Settings::set_file_loader(godot_file_loader);
    auto result = leanclr::vm::Runtime::initialize();
    if (result.is_err())
    {
        last_error() = ("LeanCLR runtime initialization failed with error " + String::num_int64(static_cast<int64_t>(result.unwrap_err()))).utf8().get_data();
        return false;
    }

    register_godot_internal_calls();
    initialized() = true;
    last_error().clear();
    return true;
}

void LeanCLRRuntimeBridge::shutdown()
{
    if (!initialized())
    {
        return;
    }

    leanclr::vm::Runtime::shutdown();
    initialized() = false;
    godot_icalls_registered() = false;
}

bool LeanCLRRuntimeBridge::is_initialized()
{
    return initialized();
}


void LeanCLRRuntimeBridge::register_script_object(Object* p_owner, void* p_managed_object)
{
    if (p_owner != nullptr && p_managed_object != nullptr)
    {
        script_objects_by_owner()[p_owner] = static_cast<leanclr::vm::RtObject*>(p_managed_object);
    }
}

void LeanCLRRuntimeBridge::unregister_script_object(Object* p_owner, void* p_managed_object)
{
    if (p_owner == nullptr)
    {
        return;
    }

    auto& objects = script_objects_by_owner();
    auto it = objects.find(p_owner);
    if (it != objects.end() && it->second == static_cast<leanclr::vm::RtObject*>(p_managed_object))
    {
        objects.erase(it);
    }
}

void* LeanCLRRuntimeBridge::get_script_object_for_owner(Object* p_owner)
{
    if (p_owner == nullptr)
    {
        return nullptr;
    }

    auto& objects = script_objects_by_owner();
    auto it = objects.find(p_owner);
    return it != objects.end() ? it->second : nullptr;
}

int32_t LeanCLRRuntimeBridge::migrate_script_state(void* p_source_object, void* p_target_object)
{
    if (p_source_object == nullptr || p_target_object == nullptr)
    {
        return 0;
    }

    leanclr::vm::RtObject* source_object = static_cast<leanclr::vm::RtObject*>(p_source_object);
    leanclr::vm::RtObject* target_object = static_cast<leanclr::vm::RtObject*>(p_target_object);
    int32_t migrated_count = 0;

    for (uint16_t i = 0; i < source_object->klass->field_count; ++i)
    {
        const leanclr::metadata::RtFieldInfo* source_field = source_object->klass->fields + i;
        if (source_field->name == nullptr || std::strcmp(source_field->name, "NativePtr") == 0 ||
            !leanclr::vm::Field::is_instance(source_field) || leanclr::vm::Field::is_static_included_literal_and_rva(source_field) ||
            !is_hot_reload_field_type_supported(source_field->type_sig))
        {
            continue;
        }

        const leanclr::metadata::RtFieldInfo* target_field = find_migratable_field_by_name(target_object->klass, source_field->name);
        if (target_field == nullptr || !are_hot_reload_field_types_compatible(source_field->type_sig, target_field->type_sig))
        {
            continue;
        }

        auto source_size = leanclr::vm::Field::get_field_size(source_field);
        auto target_size = leanclr::vm::Field::get_field_size(target_field);
        if (source_size.is_err() || target_size.is_err() || source_size.unwrap() != target_size.unwrap())
        {
            continue;
        }

        std::vector<uint8_t> value(source_size.unwrap());
        if (leanclr::vm::Field::get_instance_value(source_field, source_object, value.data()).is_err() ||
            leanclr::vm::Field::set_instance_value(target_field, target_object, value.data()).is_err())
        {
            continue;
        }
        ++migrated_count;
    }

    return migrated_count;
}

bool LeanCLRRuntimeBridge::load_assembly(const String& p_assembly_name)
{
    if (!initialize())
    {
        return false;
    }

    const CharString assembly_name = p_assembly_name.utf8();
    auto result = leanclr::vm::Assembly::load_by_name(assembly_name.get_data());
    if (result.is_err())
    {
        last_error() = ("Failed to load LeanCLR assembly '" + p_assembly_name + "' with error " +
                        String::num_int64(static_cast<int64_t>(result.unwrap_err()))).utf8().get_data();
        return false;
    }

    last_error().clear();
    return true;
}

void* LeanCLRRuntimeBridge::create_script_object(const String& p_assembly_name, const String& p_type_name, Object* p_owner)
{
    if (!initialize())
    {
        return nullptr;
    }

    leanclr::metadata::RtModuleDef* module = load_module(p_assembly_name);
    if (module == nullptr)
    {
        return nullptr;
    }

    leanclr::metadata::RtClass* klass = find_class(module, p_type_name);
    if (klass == nullptr)
    {
        return nullptr;
    }

    auto object_result = leanclr::vm::Object::new_object(klass);
    if (object_result.is_err())
    {
        last_error() = ("Failed to create LeanCLR object '" + p_type_name + "' with error " +
                        String::num_int64(static_cast<int64_t>(object_result.unwrap_err()))).utf8().get_data();
        return nullptr;
    }

    leanclr::vm::RtObject* object = object_result.unwrap();
    if (!attach_native_owner(object, p_owner))
    {
        return nullptr;
    }

    const leanclr::metadata::RtMethodInfo* ctor = leanclr::vm::Method::find_matched_method_in_class_by_name(klass, ".ctor");
    if (ctor != nullptr)
    {
        auto ctor_result = leanclr::vm::Runtime::invoke_with_run_cctor(ctor, object, nullptr);
        if (ctor_result.is_err())
        {
            last_error() = ("Failed to run LeanCLR constructor for '" + p_type_name + "' with error " +
                            String::num_int64(static_cast<int64_t>(ctor_result.unwrap_err()))).utf8().get_data();
            return nullptr;
        }
    }

    last_error().clear();
    return object;
}

void LeanCLRRuntimeBridge::release_script_object(void* p_managed_object)
{
    (void)p_managed_object;
}

bool LeanCLRRuntimeBridge::has_script_method(void* p_managed_object, const String& p_method, int32_t p_argument_count)
{
    if (p_managed_object == nullptr)
    {
        return false;
    }

    leanclr::vm::RtObject* object = static_cast<leanclr::vm::RtObject*>(p_managed_object);
    const CharString method_name = p_method.utf8();
    return leanclr::vm::Method::find_matched_method_in_class_by_name_and_param_count(object->klass, method_name.get_data(),
                                                                                      static_cast<size_t>(p_argument_count)) != nullptr;
}

bool LeanCLRRuntimeBridge::invoke_script_method(void* p_managed_object, const String& p_method)
{
    if (p_managed_object == nullptr)
    {
        last_error() = "LeanCLR script instance has no managed object.";
        return false;
    }

    leanclr::vm::RtObject* object = static_cast<leanclr::vm::RtObject*>(p_managed_object);
    const CharString method_name = p_method.utf8();
    const leanclr::metadata::RtMethodInfo* method =
        leanclr::vm::Method::find_matched_method_in_class_by_name_and_param_count(object->klass, method_name.get_data(), 0);
    if (method == nullptr)
    {
        last_error().clear();
        return true;
    }

    auto invoke_result = leanclr::vm::Runtime::invoke_with_run_cctor(method, object, nullptr);
    if (invoke_result.is_err())
    {
        last_error() = ("Failed to invoke LeanCLR " + p_method + " with error " + String::num_int64(static_cast<int64_t>(invoke_result.unwrap_err()))).utf8().get_data();
        return false;
    }

    last_error().clear();
    return true;
}

leanclr::vm::RtObject* create_managed_godot_object(const String& p_type_name, Object* p_owner)
{
    leanclr::metadata::RtModuleDef* module = load_module("GodotSharpCompat");
    if (module == nullptr)
    {
        return nullptr;
    }

    leanclr::metadata::RtClass* klass = find_class(module, p_type_name);
    if (klass == nullptr)
    {
        return nullptr;
    }

    auto object_result = leanclr::vm::Object::new_object(klass);
    if (object_result.is_err())
    {
        last_error() = ("Failed to create LeanCLR Godot object '" + p_type_name + "' with error " +
                        String::num_int64(static_cast<int64_t>(object_result.unwrap_err()))).utf8().get_data();
        return nullptr;
    }

    leanclr::vm::RtObject* object = object_result.unwrap();
    return attach_native_owner(object, p_owner) ? object : nullptr;
}

bool LeanCLRRuntimeBridge::invoke_script_method(void* p_managed_object, const String& p_method, double p_argument)
{
    if (p_managed_object == nullptr)
    {
        last_error() = "LeanCLR script instance has no managed object.";
        return false;
    }

    leanclr::vm::RtObject* object = static_cast<leanclr::vm::RtObject*>(p_managed_object);
    const CharString method_name = p_method.utf8();
    const leanclr::metadata::RtMethodInfo* method =
        leanclr::vm::Method::find_matched_method_in_class_by_name_and_param_count(object->klass, method_name.get_data(), 1);
    if (method == nullptr)
    {
        last_error().clear();
        return true;
    }

    const void* params[] = {&p_argument};
    auto invoke_result = leanclr::vm::Runtime::invoke_with_run_cctor(method, object, params);
    if (invoke_result.is_err())
    {
        last_error() = ("Failed to invoke LeanCLR " + p_method + " with error " + String::num_int64(static_cast<int64_t>(invoke_result.unwrap_err()))).utf8().get_data();
        return false;
    }

    last_error().clear();
    return true;
}

bool LeanCLRRuntimeBridge::invoke_script_method(void* p_managed_object, const String& p_method, float p_argument)
{
    if (p_managed_object == nullptr)
    {
        last_error() = "LeanCLR script instance has no managed object.";
        return false;
    }

    leanclr::vm::RtObject* object = static_cast<leanclr::vm::RtObject*>(p_managed_object);
    const CharString method_name = p_method.utf8();
    const leanclr::metadata::RtMethodInfo* method =
        leanclr::vm::Method::find_matched_method_in_class_by_name_and_param_count(object->klass, method_name.get_data(), 1);
    if (method == nullptr)
    {
        last_error().clear();
        return true;
    }

    const void* params[] = {&p_argument};
    auto invoke_result = leanclr::vm::Runtime::invoke_with_run_cctor(method, object, params);
    if (invoke_result.is_err())
    {
        last_error() = ("Failed to invoke LeanCLR " + p_method + " with error " + String::num_int64(static_cast<int64_t>(invoke_result.unwrap_err()))).utf8().get_data();
        return false;
    }

    last_error().clear();
    return true;
}


bool LeanCLRRuntimeBridge::invoke_script_method(void* p_managed_object, const String& p_method, const Variant& p_argument)
{
    return invoke_script_method(p_managed_object, p_method, &p_argument, 1, nullptr);
}

bool LeanCLRRuntimeBridge::invoke_script_method(void* p_managed_object, const String& p_method, const Variant* p_arguments, int32_t p_argument_count)
{
    return invoke_script_method(p_managed_object, p_method, p_arguments, p_argument_count, nullptr);
}

bool LeanCLRRuntimeBridge::invoke_script_method(void* p_managed_object, const String& p_method, const Variant* p_arguments, int32_t p_argument_count, Variant* r_return)
{
    if (p_managed_object == nullptr)
    {
        last_error() = "LeanCLR script instance has no managed object.";
        return false;
    }

    leanclr::vm::RtObject* object = static_cast<leanclr::vm::RtObject*>(p_managed_object);
    const leanclr::metadata::RtMethodInfo* method = find_compatible_script_method(object, p_method, p_arguments, p_argument_count);
    if (method == nullptr)
    {
        last_error().clear();
        return true;
    }

    return invoke_script_method_with_method(object, p_method, method, p_arguments, p_argument_count, r_return);
}

bool LeanCLRRuntimeBridge::invoke_script_method(void* p_managed_object, const String& p_method, InputEvent* p_argument)
{
    if (p_managed_object == nullptr)
    {
        last_error() = "LeanCLR script instance has no managed object.";
        return false;
    }

    leanclr::vm::RtObject* object = static_cast<leanclr::vm::RtObject*>(p_managed_object);
    const CharString method_name = p_method.utf8();
    const leanclr::metadata::RtMethodInfo* method =
        leanclr::vm::Method::find_matched_method_in_class_by_name_and_param_count(object->klass, method_name.get_data(), 1);
    if (method == nullptr)
    {
        last_error().clear();
        return true;
    }

    leanclr::vm::RtObject* event_object = create_managed_godot_object("Godot.InputEvent", p_argument);
    if (event_object == nullptr)
    {
        return false;
    }

    const void* params[] = {event_object};
    auto invoke_result = leanclr::vm::Runtime::invoke_with_run_cctor(method, object, params);
    if (invoke_result.is_err())
    {
        last_error() = ("Failed to invoke LeanCLR " + p_method + " with error " + String::num_int64(static_cast<int64_t>(invoke_result.unwrap_err()))).utf8().get_data();
        return false;
    }

    last_error().clear();
    return true;
}


bool LeanCLRRuntimeBridge::get_script_property(void* p_managed_object, const String& p_property, Variant* r_value)
{
    leanclr::vm::RtObject* object = static_cast<leanclr::vm::RtObject*>(p_managed_object);
    const leanclr::metadata::RtPropertyInfo* property = find_script_property(object, p_property);
    if (!is_script_property_visible(property))
    {
        return false;
    }

    auto invoke_result = leanclr::vm::Runtime::invoke_with_run_cctor(property->get_method, object, nullptr);
    if (invoke_result.is_err())
    {
        last_error() = ("Failed to get LeanCLR property " + p_property + " with error " + String::num_int64(static_cast<int64_t>(invoke_result.unwrap_err()))).utf8().get_data();
        return false;
    }

    if (r_value != nullptr)
    {
        *r_value = return_object_to_variant(property->property_sig.type_sig, invoke_result.unwrap());
    }
    last_error().clear();
    return true;
}

bool LeanCLRRuntimeBridge::set_script_property(void* p_managed_object, const String& p_property, const Variant& p_value)
{
    leanclr::vm::RtObject* object = static_cast<leanclr::vm::RtObject*>(p_managed_object);
    const leanclr::metadata::RtPropertyInfo* property = find_script_property(object, p_property);
    if (!is_script_property_visible(property) || !can_convert_variant_to_parameter(p_value, property->set_method->parameters[0]))
    {
        return false;
    }

    ScriptArgumentStorage storage;
    if (!fill_script_argument_storage(p_value, property->set_method->parameters[0], storage))
    {
        return false;
    }
    const void* params[] = {storage.pointer};
    auto invoke_result = leanclr::vm::Runtime::invoke_with_run_cctor(property->set_method, object, params);
    if (invoke_result.is_err())
    {
        last_error() = ("Failed to set LeanCLR property " + p_property + " with error " + String::num_int64(static_cast<int64_t>(invoke_result.unwrap_err()))).utf8().get_data();
        return false;
    }
    last_error().clear();
    return true;
}

bool LeanCLRRuntimeBridge::get_script_property_list(void* p_managed_object, std::vector<LeanCLRScriptPropertyInfo>& r_properties)
{
    leanclr::vm::RtObject* object = static_cast<leanclr::vm::RtObject*>(p_managed_object);
    if (object == nullptr || object->klass == nullptr)
    {
        return false;
    }

    for (const leanclr::metadata::RtClass* klass = object->klass; klass != nullptr; klass = klass->parent)
    {
        for (uint16_t i = 0; i < klass->property_count; ++i)
        {
            const leanclr::metadata::RtPropertyInfo* property = &klass->properties[i];
            if (!is_script_property_visible(property))
            {
                continue;
            }
            LeanCLRScriptPropertyInfo info;
            info.name = property->name != nullptr ? String(property->name) : String();
            info.type = static_cast<int32_t>(managed_type_to_variant_type(property->property_sig.type_sig));
            get_export_attribute_metadata(property, info);
            r_properties.push_back(info);
        }
    }
    return true;
}

int32_t LeanCLRRuntimeBridge::get_script_property_type(void* p_managed_object, const String& p_property, bool* r_is_valid)
{
    leanclr::vm::RtObject* object = static_cast<leanclr::vm::RtObject*>(p_managed_object);
    const leanclr::metadata::RtPropertyInfo* property = find_script_property(object, p_property);
    const bool valid = is_script_property_visible(property);
    if (r_is_valid != nullptr)
    {
        *r_is_valid = valid;
    }
    return valid ? static_cast<int32_t>(managed_type_to_variant_type(property->property_sig.type_sig)) : static_cast<int32_t>(Variant::NIL);
}

bool LeanCLRRuntimeBridge::invoke_script_ready(void* p_managed_object)
{
    return invoke_script_method(p_managed_object, "_Ready");
}

bool LeanCLRRuntimeBridge::invoke_script_process(void* p_managed_object, double p_delta)
{
    return invoke_script_method(p_managed_object, "_Process", p_delta);
}

bool LeanCLRRuntimeBridge::invoke_static_entry(const String& p_assembly_name, const String& p_entry_point)
{
    if (p_entry_point.is_empty())
    {
        return load_assembly(p_assembly_name);
    }

    if (!initialize())
    {
        return false;
    }

    const CharString assembly_name = p_assembly_name.utf8();
    auto assembly_result = leanclr::vm::Assembly::load_by_name(assembly_name.get_data());
    if (assembly_result.is_err())
    {
        last_error() = ("Failed to load LeanCLR assembly '" + p_assembly_name + "' with error " +
                        String::num_int64(static_cast<int64_t>(assembly_result.unwrap_err()))).utf8().get_data();
        return false;
    }

    const int64_t separator = p_entry_point.find("::");
    if (separator < 0)
    {
        last_error() = "LeanCLR entry point must use <namespace.type>::<method>.";
        return false;
    }

    const CharString class_name = p_entry_point.substr(0, separator).utf8();
    const CharString method_name = p_entry_point.substr(separator + 2).utf8();
    leanclr::metadata::RtModuleDef* module = assembly_result.unwrap()->mod;

    auto class_result = module->get_class_by_nested_full_name(class_name.get_data(), false, true);
    if (class_result.is_err())
    {
        last_error() = ("Failed to find LeanCLR class '" + p_entry_point.substr(0, separator) + "' with error " +
                        String::num_int64(static_cast<int64_t>(class_result.unwrap_err()))).utf8().get_data();
        return false;
    }

    leanclr::metadata::RtClass* klass = class_result.unwrap();
    auto initialize_result = leanclr::vm::Class::initialize_all(klass);
    if (initialize_result.is_err())
    {
        last_error() = ("Failed to initialize LeanCLR class '" + p_entry_point.substr(0, separator) + "' with error " +
                        String::num_int64(static_cast<int64_t>(initialize_result.unwrap_err()))).utf8().get_data();
        return false;
    }

    const leanclr::metadata::RtMethodInfo* method = leanclr::vm::Method::find_matched_method_in_class_by_name(klass, method_name.get_data());
    if (method == nullptr)
    {
        last_error() = ("Failed to find LeanCLR method '" + p_entry_point + "'.").utf8().get_data();
        return false;
    }

    if (!leanclr::vm::Method::is_static(method) || leanclr::vm::Method::get_param_count_include_this(method) != 0 ||
        leanclr::vm::Method::contains_not_instantiated_generic_param(method))
    {
        last_error() = ("LeanCLR entry point must be a non-generic static method with no parameters: " + p_entry_point).utf8().get_data();
        return false;
    }

    auto invoke_result = leanclr::vm::Runtime::invoke_array_arguments_with_run_cctor(method, nullptr, nullptr);
    if (invoke_result.is_err())
    {
        last_error() = ("Failed to invoke LeanCLR entry point '" + p_entry_point + "' with error " +
                        String::num_int64(static_cast<int64_t>(invoke_result.unwrap_err()))).utf8().get_data();
        return false;
    }

    leanclr::vm::RtObject* result = invoke_result.unwrap();
    if (result != nullptr && result->klass->by_val->ele_type == leanclr::metadata::RtElementType::String)
    {
        UtilityFunctions::print("LeanCLR: ", rt_string_to_godot(reinterpret_cast<leanclr::vm::RtString*>(result)));
    }
    else
    {
        UtilityFunctions::print("LeanCLR entry invoked: ", p_entry_point);
    }

    last_error().clear();
    return true;
}

String LeanCLRRuntimeBridge::get_last_error()
{
    return String(last_error().c_str());
}

} // namespace godot
