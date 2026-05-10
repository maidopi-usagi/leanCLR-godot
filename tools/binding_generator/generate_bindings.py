#!/usr/bin/env python3
import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


SMOKE_TEST_CLASSES = ["Object", "RefCounted", "Resource", "MainLoop", "SceneTree", "Node", "CanvasItem", "Node2D", "Control", "Label", "Sprite2D"]
CS_CLASS_NAMES = {"Object": "GodotObject"}
CPP_HEADER_NAME_OVERRIDES = {
    "Object": "object",
    "RefCounted": "ref_counted",
    "Resource": "resource",
    "MainLoop": "main_loop",
    "SceneTree": "scene_tree",
    "Node": "node",
    "CanvasItem": "canvas_item",
    "Node2D": "node2d",
    "Control": "control",
    "Label": "label",
    "Sprite2D": "sprite2d",
    "AnimationNodeBlendSpace1D": "animation_node_blend_space1_d",
    "ClassDB": "class_db_singleton",
    "EditorSceneFormatImporterFBX2GLTF": "editor_scene_format_importer_fbx2_gltf",
    "Generic6DOFJoint3D": "generic6_dof_joint3d",
    "GradientTexture1D": "gradient_texture1_d",
}
HANDWRITTEN_PARTIAL_CLASSES = {"GodotObject", "Node"}
CS_KEYWORDS = {
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char", "checked", "class", "const",
    "continue", "decimal", "default", "delegate", "do", "double", "else", "enum", "event", "explicit", "extern",
    "false", "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit", "in", "int", "interface",
    "internal", "is", "lock", "long", "namespace", "new", "null", "object", "operator", "out", "override",
    "params", "private", "protected", "public", "readonly", "ref", "return", "sbyte", "sealed", "short", "sizeof",
    "stackalloc", "static", "string", "struct", "switch", "this", "throw", "true", "try", "typeof", "uint", "ulong",
    "unchecked", "unsafe", "ushort", "using", "virtual", "void", "volatile", "while",
}

PROPERTY_METHODS = {
    ("Node", "get_name"),
    ("Node", "set_name"),
    ("Node2D", "get_position"),
    ("Node2D", "set_position"),
    ("Node2D", "get_global_position"),
    ("Node2D", "set_global_position"),
    ("Node2D", "get_scale"),
    ("Node2D", "set_scale"),
    ("Control", "get_position"),
    ("Control", "set_position"),
    ("Control", "get_size"),
    ("Control", "set_size"),
    ("Label", "get_text"),
    ("Label", "set_text"),
    ("Sprite2D", "is_centered"),
    ("Sprite2D", "set_centered"),
    ("Sprite2D", "get_offset"),
    ("Sprite2D", "set_offset"),
    ("Sprite2D", "is_flipped_h"),
    ("Sprite2D", "set_flip_h"),
    ("Sprite2D", "is_flipped_v"),
    ("Sprite2D", "set_flip_v"),
}

EXCLUDED_METHODS = set()

METHOD_ALIASES = {
    ("Object", "to_string"): "ToGodotString",
    ("Node", "get_node"): "GetNode",
    ("Node", "get_node_or_null"): "GetNodeOrNull",
}

ICALL_SUFFIX_ALIASES = {
    ("Node", "get_node"): "GetNode",
    ("Node", "get_node_or_null"): "GetNodeOrNull",
}

CPP_METHOD_ALIASES = {
    ("Node", "get_node"): "get_node<Node>",
    ("Node", "get_node_or_null"): "get_node_or_null",
    ("TextServer", "shaped_get_run_glyph_range"): "shaped_get_run_range",
}

METHOD_ARGUMENT_TYPE_OVERRIDES = {
    ("FileAccess", "create_temp", "mode_flags"): ("enum::FileAccess.ModeFlags", None),
}

STRING_LIKE_TYPES = {"String", "StringName", "NodePath"}
PACKED_ARRAY_TYPES = {
    "PackedByteArray", "PackedInt32Array", "PackedInt64Array", "PackedFloat32Array", "PackedFloat64Array",
    "PackedVector2Array", "PackedVector3Array", "PackedColorArray",
}
OPAQUE_VARIANT_TYPES = {"Array", "Dictionary", "Callable", "Signal"}
OPAQUE_VALUE_TYPES = set()
INT32_META = {"int8", "uint8", "int16", "uint16", "int32", "uint32", "char16", "char32"}
INT64_META = {"int64", "uint64"}
CPP_INT_TYPES = {
    "int8": "int8_t",
    "uint8": "uint8_t",
    "int16": "int16_t",
    "uint16": "uint16_t",
    "int32": "int32_t",
    "uint32": "uint32_t",
    "char16": "char16_t",
    "char32": "char32_t",
    "int64": "int64_t",
    "uint64": "uint64_t",
}

PACKED_ARRAY_INFOS = {
    "PackedByteArray": {"cs": "byte", "cpp": "PackedByteArray", "stack": "uint8_t", "default": "0"},
    "PackedInt32Array": {"cs": "int", "cpp": "PackedInt32Array", "stack": "int32_t", "default": "0"},
    "PackedInt64Array": {"cs": "long", "cpp": "PackedInt64Array", "stack": "int64_t", "default": "0"},
    "PackedFloat32Array": {"cs": "float", "cpp": "PackedFloat32Array", "stack": "float", "default": "0.0f"},
    "PackedFloat64Array": {"cs": "double", "cpp": "PackedFloat64Array", "stack": "double", "default": "0.0"},
    "PackedVector2Array": {"cs": "Vector2", "cpp": "PackedVector2Array", "stack": "Vector2", "default": "Vector2()"},
    "PackedVector3Array": {"cs": "Vector3", "cpp": "PackedVector3Array", "stack": "Vector3", "default": "Vector3()"},
    "PackedColorArray": {"cs": "Color", "cpp": "PackedColorArray", "stack": "Color", "default": "Color()"},
}


@dataclass(frozen=True)
class TypeInfo:
    managed_type: str
    native_type: str
    stack_type: str
    signature_type: str
    category: str
    cpp_type: str = ""
    cs_class: str = ""
    stack_slots: int = 1


@dataclass(frozen=True)
class GeneratedMethod:
    class_name: str
    cs_class_name: str
    cpp_class_name: str
    api_name: str
    cpp_name: str
    cs_name: str
    icall_suffix: str
    return_type: TypeInfo
    args: tuple
    is_static: bool
    is_virtual: bool = False
    is_vararg: bool = False


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    with path.open("w", encoding="utf-8", newline="") as file:
        file.write(normalized.replace("\n", "\r\n"))


def cs_class_name(class_name):
    return cs_identifier(CS_CLASS_NAMES.get(class_name, class_name), "GodotType")


def cs_identifier(name, fallback):
    identifier = re.sub(r"[^0-9A-Za-z_]", "_", name)
    if not identifier:
        identifier = fallback
    if identifier[0].isdigit():
        identifier = f"{fallback}{identifier}"
    if identifier.lower() in CS_KEYWORDS:
        identifier = f"{identifier}_"
    return identifier


def pascal_name(snake_name):
    return cs_identifier("".join(part.capitalize() for part in snake_name.split("_") if part), "Value")


def camel_name(snake_name):
    pascal = pascal_name(snake_name)
    return pascal[:1].lower() + pascal[1:]


def native_function_name(method):
    return f"godot_{method.cs_class_name}_{method.icall_suffix}".lower()


def cpp_header_name(class_name):
    if class_name in CPP_HEADER_NAME_OVERRIDES:
        return CPP_HEADER_NAME_OVERRIDES[class_name]
    header = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", class_name)
    header = re.sub(r"([a-z])([A-Z])", r"\1_\2", header)
    return header.lower()


def icall_name(method):
    param_types = [] if method.is_static else ["System.IntPtr"]
    param_sig = ",".join(param_types + [arg["type"].signature_type for arg in method.args])
    if method.is_vararg:
        param_sig = param_sig + ("," if param_sig else "") + "Godot.Variant[]"
    return f"Godot.NativeCalls::Godot{method.cs_class_name}{method.icall_suffix}({param_sig})"


def class_inherits(class_name, base_name, classes):
    current = classes.get(class_name, {}).get("inherits")
    while current:
        if current == base_name:
            return True
        current = classes.get(current, {}).get("inherits")
    return False


def method_type_info(raw_type, meta, class_names, classes=None, global_enum_names=None, global_bitfield_names=None):
    if raw_type is None:
        return TypeInfo("void", "leanclr::RtResultVoid", "", "", "void", stack_slots=0)
    if raw_type == "bool":
        return TypeInfo("bool", "bool", "bool", "System.Boolean", "bool")
    if raw_type == "float":
        return TypeInfo("float", "float", "float", "System.Single", "float")
    if raw_type == "int":
        if meta in INT32_META:
            return TypeInfo("int", "int32_t", "int32_t", "System.Int32", "int", cpp_type=CPP_INT_TYPES[meta])
        if meta in INT64_META:
            return TypeInfo("long", "int64_t", "int64_t", "System.Int64", "int", cpp_type=CPP_INT_TYPES[meta])
        return TypeInfo("long", "int64_t", "int64_t", "System.Int64", "int")
    if raw_type in STRING_LIKE_TYPES:
        managed_type = "string" if raw_type == "String" else raw_type
        return TypeInfo(managed_type, "leanclr::vm::RtString*", "leanclr::vm::RtString*", "System.String", "string", cpp_type=raw_type)
    if raw_type == "Variant":
        return TypeInfo("Variant", "ManagedVariant", "ManagedVariant", "Godot.Variant", "variant", cpp_type="Variant", stack_slots=9)
    if raw_type == "PackedStringArray":
        return TypeInfo("PackedStringArray", "intptr_t", "intptr_t", "System.IntPtr", "packed_string_array", cpp_type="PackedStringArray")
    if raw_type in PACKED_ARRAY_TYPES:
        return TypeInfo(raw_type, "intptr_t", "intptr_t", "System.IntPtr", "packed_array", cpp_type=raw_type, cs_class=raw_type)
    if raw_type in OPAQUE_VARIANT_TYPES:
        return TypeInfo(raw_type, "intptr_t", "intptr_t", "System.IntPtr", "opaque_variant", cpp_type=raw_type, cs_class=raw_type)
    if raw_type and raw_type.startswith("typedarray::"):
        element_type = raw_type.removeprefix("typedarray::")
        cpp_element_type = element_type
        if element_type == "Object":
            cpp_element_type = "Object"
        return TypeInfo("GodotArray", "intptr_t", "intptr_t", "System.IntPtr", "typed_array", cpp_type=f"TypedArray<{cpp_element_type}>", cs_class="GodotArray")
    if raw_type in OPAQUE_VALUE_TYPES:
        return TypeInfo(raw_type, "intptr_t", "intptr_t", "System.IntPtr", "opaque_value", cpp_type=raw_type, cs_class=raw_type)
    if raw_type in {"const void*", "const GDExtensionInitializationFunction*"} or (raw_type and raw_type.endswith("*")):
        return TypeInfo("IntPtr", "intptr_t", "intptr_t", "System.IntPtr", "native_pointer", cpp_type=raw_type)
    if raw_type == "Vector2":
        return TypeInfo("Vector2", "Vector2", "Vector2", "Godot.Vector2", "vector2", cpp_type="Vector2")
    if raw_type == "Vector2i":
        return TypeInfo("Vector2i", "Vector2i", "Vector2i", "Godot.Vector2i", "vector2i", cpp_type="Vector2i")
    if raw_type == "Vector3":
        return TypeInfo("Vector3", "Vector3", "Vector3", "Godot.Vector3", "vector3", cpp_type="Vector3", stack_slots=2)
    if raw_type == "Vector3i":
        return TypeInfo("Vector3i", "Vector3i", "Vector3i", "Godot.Vector3i", "vector3i", cpp_type="Vector3i", stack_slots=2)
    if raw_type == "Color":
        return TypeInfo("Color", "Color", "Color", "Godot.Color", "color", cpp_type="Color", stack_slots=2)
    if raw_type == "Rect2":
        return TypeInfo("Rect2", "Rect2", "Rect2", "Godot.Rect2", "rect2", cpp_type="Rect2", stack_slots=2)
    if raw_type == "Rect2i":
        return TypeInfo("Rect2i", "Rect2i", "Rect2i", "Godot.Rect2i", "rect2i", cpp_type="Rect2i", stack_slots=2)
    if raw_type == "Transform2D":
        return TypeInfo("Transform2D", "Transform2D", "Transform2D", "Godot.Transform2D", "transform2d", cpp_type="Transform2D", stack_slots=3)
    if raw_type == "AABB":
        return TypeInfo("Aabb", "AABB", "AABB", "Godot.Aabb", "aabb", cpp_type="AABB", stack_slots=3)
    if raw_type == "Quaternion":
        return TypeInfo("Quaternion", "Quaternion", "Quaternion", "Godot.Quaternion", "quaternion", cpp_type="Quaternion", stack_slots=2)
    if raw_type == "Basis":
        return TypeInfo("Basis", "Basis", "Basis", "Godot.Basis", "basis", cpp_type="Basis", stack_slots=5)
    if raw_type == "Transform3D":
        return TypeInfo("Transform3D", "Transform3D", "Transform3D", "Godot.Transform3D", "transform3d", cpp_type="Transform3D", stack_slots=6)
    if raw_type == "Vector4":
        return TypeInfo("Vector4", "Vector4", "Vector4", "Godot.Vector4", "vector4", cpp_type="Vector4", stack_slots=2)
    if raw_type == "Vector4i":
        return TypeInfo("Vector4i", "Vector4i", "Vector4i", "Godot.Vector4i", "vector4i", cpp_type="Vector4i", stack_slots=2)
    if raw_type == "Plane":
        return TypeInfo("Plane", "Plane", "Plane", "Godot.Plane", "plane", cpp_type="Plane", stack_slots=2)
    if raw_type == "Projection":
        return TypeInfo("Projection", "Projection", "Projection", "Godot.Projection", "projection", cpp_type="Projection", stack_slots=8)
    if raw_type == "RID":
        return TypeInfo("RID", "RID", "RID", "Godot.RID", "rid", cpp_type="RID")
    if raw_type and raw_type.startswith("enum::"):
        enum_name = raw_type.removeprefix("enum::")
        if "." not in enum_name:
            if global_enum_names is not None and enum_name in global_enum_names:
                managed_name = cs_identifier(enum_name, "GodotEnum")
                return TypeInfo(managed_name, "int32_t", "int32_t", "System.Int32", "enum", cpp_type=enum_name)
            return TypeInfo("", "", "", "", "unsupported")
        class_name, nested_name = enum_name.split(".", 1)
        managed_name = f"{cs_class_name(class_name)}.{cs_identifier(nested_name, 'GodotEnum')}"
        return TypeInfo(managed_name, "int32_t", "int32_t", "System.Int32", "enum", cpp_type=enum_name.replace(".", "::"))
    if raw_type and raw_type.startswith("bitfield::"):
        bitfield_name = raw_type.removeprefix("bitfield::")
        if "." not in bitfield_name:
            if global_bitfield_names is not None and bitfield_name in global_bitfield_names:
                managed_name = cs_identifier(bitfield_name, "GodotBitfield")
                return TypeInfo(managed_name, "int64_t", "int64_t", "System.Int64", "bitfield", cpp_type=f"BitField<{bitfield_name}>")
            return TypeInfo("", "", "", "", "unsupported")
        class_name, nested_name = bitfield_name.split(".", 1)
        cpp_enum_name = bitfield_name.replace(".", "::")
        managed_name = f"{cs_class_name(class_name)}.{cs_identifier(nested_name, 'GodotBitfield')}"
        return TypeInfo(managed_name, "int64_t", "int64_t", "System.Int64", "bitfield", cpp_type=f"BitField<{cpp_enum_name}>")
    if raw_type in class_names:
        if classes is not None and (raw_type == "RefCounted" or class_inherits(raw_type, "RefCounted", classes)):
            return TypeInfo(cs_class_name(raw_type), "intptr_t", "intptr_t", "System.IntPtr", "refcounted", cpp_type=raw_type, cs_class=cs_class_name(raw_type))
        return TypeInfo(cs_class_name(raw_type), "intptr_t", "intptr_t", "System.IntPtr", "object", cpp_type=raw_type, cs_class=cs_class_name(raw_type))
    return TypeInfo("", "", "", "", "unsupported")


def is_supported_type(type_info):
    return type_info.category in {"void", "bool", "float", "int", "string", "variant", "packed_string_array", "packed_array", "opaque_variant", "typed_array", "opaque_value", "native_pointer", "object", "refcounted", "enum", "bitfield", "vector2", "vector2i", "vector3", "vector3i", "color", "rect2", "rect2i", "transform2d", "aabb", "quaternion", "basis", "transform3d", "vector4", "vector4i", "plane", "projection", "rid"}


def empty_report(class_order):
    return {
        "class_count": len(class_order),
        "generated_managed_classes": len(class_order),
        "native_bound_classes": [],
        "generated_methods": 0,
        "skipped_methods": {},
        "unsupported_type_counts": {},
        "overview": {},
        "per_class": [],
        "examples": {},
    }


def add_report_skip(report, reason, example, raw_type=None):
    report["skipped_methods"][reason] = report["skipped_methods"].get(reason, 0) + 1
    examples = report["examples"].setdefault(reason, [])
    if len(examples) < 20:
        examples.append(example)
    if raw_type:
        report["unsupported_type_counts"][raw_type] = report["unsupported_type_counts"].get(raw_type, 0) + 1


def method_example(class_name, method):
    return f"{class_name}.{method['name']}"


def method_skip_reason(class_name, method, class_names, classes, global_enum_names, global_bitfield_names):
    if (class_name, method["name"]) in EXCLUDED_METHODS:
        return "excluded_method", None
    if method.get("is_vararg"):
        return "vararg_method", None
    if method.get("is_virtual"):
        return "virtual_method", None
    return_value = method.get("return_value") or {}
    return_type = method_type_info(return_value.get("type"), return_value.get("meta"), class_names, classes, global_enum_names, global_bitfield_names)
    if not is_supported_type(return_type):
        return "unsupported_return", return_value.get("type")
    for arg in method.get("arguments", []):
        if "default_value" in arg:
            continue
        raw_type, meta = METHOD_ARGUMENT_TYPE_OVERRIDES.get((class_name, method["name"], arg["name"]), (arg["type"], arg.get("meta")))
        arg_type = method_type_info(raw_type, meta, class_names, classes, global_enum_names, global_bitfield_names)
        if not is_supported_type(arg_type) or arg_type.category == "void":
            return "unsupported_argument", arg.get("type")
    return "supported_signature_not_selected", None


def build_generated_method(class_name, api_method, class_names, classes, global_enum_names, global_bitfield_names):
    if (class_name, api_method["name"]) in EXCLUDED_METHODS:
        return None, "excluded_method", None
    is_vararg = bool(api_method.get("is_vararg"))
    is_virtual = bool(api_method.get("is_virtual"))

    return_value = api_method.get("return_value") or {}
    return_type = method_type_info(return_value.get("type"), return_value.get("meta"), class_names, classes, global_enum_names, global_bitfield_names)
    if not is_supported_type(return_type):
        return None, "unsupported_return", return_value.get("type")

    args = []
    for arg in api_method.get("arguments", []):
        if "default_value" in arg:
            continue
        raw_type, meta = METHOD_ARGUMENT_TYPE_OVERRIDES.get((class_name, api_method["name"], arg["name"]), (arg["type"], arg.get("meta")))
        arg_type = method_type_info(raw_type, meta, class_names, classes, global_enum_names, global_bitfield_names)
        if not is_supported_type(arg_type) or arg_type.category == "void":
            return None, "unsupported_argument", arg.get("type")
        args.append({"name": arg["name"], "type": arg_type})

    api_name = api_method["name"]
    if is_virtual and api_name.startswith("_"):
        cs_name = "_" + pascal_name(api_name[1:])
    else:
        cs_name = METHOD_ALIASES.get((class_name, api_name), pascal_name(api_name))
    icall_suffix = ICALL_SUFFIX_ALIASES.get((class_name, api_name), cs_name)
    cpp_name = CPP_METHOD_ALIASES.get((class_name, api_name), api_name)
    return GeneratedMethod(
        class_name=class_name,
        cs_class_name=cs_class_name(class_name),
        cpp_class_name=class_name,
        api_name=api_name,
        cpp_name=cpp_name,
        cs_name=cs_name,
        icall_suffix=icall_suffix,
        return_type=return_type,
        args=tuple(args),
        is_static=bool(api_method.get("is_static")),
        is_virtual=is_virtual,
        is_vararg=is_vararg,
    ), None, None


def build_model(api):
    classes = {entry["name"]: entry for entry in api["classes"]}
    class_order = [entry["name"] for entry in api["classes"]]
    class_names = set(classes.keys())
    global_enums = api.get("global_enums", [])
    global_enum_names = {entry["name"] for entry in global_enums if not entry.get("is_bitfield")}
    global_bitfield_names = {entry["name"] for entry in global_enums if entry.get("is_bitfield")}
    missing_classes = [name for name in SMOKE_TEST_CLASSES if name not in classes]
    if missing_classes:
        raise SystemExit("extension_api.json is missing required classes: " + ", ".join(missing_classes))

    methods = []
    report = empty_report(class_order)
    generated_signatures = set()
    per_class = {name: {"class_name": name, "methods_total": len(classes[name].get("methods", [])), "methods_generated": 0, "methods_skipped": 0, "skip_reasons": {}} for name in class_order}
    for class_name in class_order:
        for api_method in classes[class_name].get("methods", []):
            method, reason, raw_type = build_generated_method(class_name, api_method, class_names, classes, global_enum_names, global_bitfield_names)
            if method is None:
                add_report_skip(report, reason, method_example(class_name, api_method), raw_type)
                per_class[class_name]["methods_skipped"] += 1
                per_class[class_name]["skip_reasons"][reason] = per_class[class_name]["skip_reasons"].get(reason, 0) + 1
                continue

            signature = (method.class_name, method.is_static, method.cs_name, tuple(arg["type"].managed_type for arg in method.args), method.is_vararg)
            if signature in generated_signatures:
                add_report_skip(report, "duplicate_managed_signature", method_example(class_name, api_method))
                per_class[class_name]["methods_skipped"] += 1
                per_class[class_name]["skip_reasons"]["duplicate_managed_signature"] = per_class[class_name]["skip_reasons"].get("duplicate_managed_signature", 0) + 1
                continue
            generated_signatures.add(signature)
            methods.append(method)
            per_class[class_name]["methods_generated"] += 1

    report["generated_methods"] = len(methods)
    native_methods = [method for method in methods if not method.is_virtual]
    native_bound_classes = sorted({method.class_name for method in native_methods})
    total_methods = sum(entry["methods_total"] for entry in per_class.values())
    skipped_methods = sum(report["skipped_methods"].values())
    report["native_bound_classes"] = native_bound_classes
    report["overview"] = {
        "api_class_count": len(class_order),
        "skeleton_class_count": len(class_order),
        "native_bound_class_count": len(native_bound_classes),
        "classes_with_generated_methods": len(native_bound_classes),
        "total_methods": total_methods,
        "generated_methods": len(methods),
        "generated_native_methods": len(native_methods),
        "generated_virtual_stubs": sum(1 for method in methods if method.is_virtual),
        "generated_vararg_bridges": sum(1 for method in methods if method.is_vararg),
        "skipped_methods": skipped_methods,
        "class_skeleton_coverage_pct": 100.0,
        "native_class_coverage_pct": round(len(native_bound_classes) * 100.0 / len(class_order), 2) if class_order else 0.0,
        "method_coverage_pct": round(len(methods) * 100.0 / total_methods, 2) if total_methods else 0.0,
    }
    class_rows = []
    for class_name in class_order:
        row = per_class[class_name]
        row["coverage_pct"] = round(row["methods_generated"] * 100.0 / row["methods_total"], 2) if row["methods_total"] else 0.0
        class_rows.append(row)
    report["per_class"] = class_rows
    return classes, class_order, global_enums, methods, report


def managed_base_clause(class_name, classes):
    cs_name = cs_class_name(class_name)
    if cs_name in HANDWRITTEN_PARTIAL_CLASSES:
        return ""
    base = classes[class_name].get("inherits")
    if not base:
        return ""
    return f" : {cs_class_name(base)}"


def managed_arg_declaration(arg):
    return f"{arg['type'].managed_type} {camel_name(arg['name'])}"


def managed_native_arg_expression(arg):
    name = camel_name(arg["name"])
    if arg["type"].category == "variant":
        return name
    if arg["type"].category in {"packed_string_array", "packed_array", "opaque_variant", "typed_array", "opaque_value"}:
        return f"{name} != null ? {name}.NativePtr : IntPtr.Zero"
    if arg["type"].category in {"object", "refcounted"}:
        return f"{name} != null ? {name}.NativePtr : IntPtr.Zero"
    if arg["type"].category == "string" and arg["type"].managed_type != "string":
        return f"{name}.ToString()"
    if arg["type"].category == "enum":
        return f"(int){name}"
    if arg["type"].category == "bitfield":
        return f"(long){name}"
    return name


def managed_return_expression(method, call):
    if method.return_type.category == "void":
        return f"            {call};"
    if method.return_type.category == "object":
        return f"            return CreateFromNative<{method.return_type.cs_class}>({call});"
    if method.return_type.category == "refcounted":
        return f"            return CreateFromNative<{method.return_type.cs_class}>({call}, true);"
    if method.return_type.category == "variant":
        return f"            return {call};"
    if method.return_type.category == "packed_string_array":
        return f"            return PackedStringArray.CreateFromNative({call});"
    if method.return_type.category in {"packed_array", "opaque_variant", "typed_array", "opaque_value"}:
        return f"            return {method.return_type.cs_class}.CreateFromNative({call});"
    if method.return_type.category == "string" and method.return_type.managed_type != "string":
        return f"            return new {method.return_type.managed_type}({call});"
    if method.return_type.category == "enum":
        return f"            return ({method.return_type.managed_type}){call};"
    if method.return_type.category == "bitfield":
        return f"            return ({method.return_type.managed_type}){call};"
    return f"            return {call};"


def managed_default_return_expression(type_info):
    category = type_info.category
    if category == "void":
        return ""
    if category == "bool":
        return "            return false;"
    if category in {"int", "enum", "bitfield"}:
        return "            return 0;"
    if category == "float":
        return "            return 0.0f;"
    if category == "string":
        return "            return string.Empty;"
    if category in {"object", "refcounted", "packed_string_array", "packed_array", "opaque_variant", "typed_array", "opaque_value"}:
        return "            return null;"
    return f"            return default({type_info.managed_type});"


def generate_managed_method(method):
    if (method.class_name, method.api_name) in PROPERTY_METHODS:
        return ""
    if method.class_name == "Node" and method.api_name in {"_ready", "_process"}:
        return ""
    if method.class_name == "Node" and method.api_name == "get_node":
        return """        public T GetNode<T>(NodePath path) where T : Node, new()
        {
            return CreateFromNative<T>(NativeCalls.GodotNodeGetNode(NativePtr, path.ToString()));
        }
"""
    if method.class_name == "Node" and method.api_name == "get_node_or_null":
        return """        public T GetNodeOrNull<T>(NodePath path) where T : Node, new()
        {
            return CreateFromNative<T>(NativeCalls.GodotNodeGetNodeOrNull(NativePtr, path.ToString()));
        }
"""

    args = ", ".join(managed_arg_declaration(arg) for arg in method.args)
    if method.is_vararg:
        args = (args + ", " if args else "") + "params Variant[] varargs"
    if method.is_virtual:
        return_type = method.return_type.managed_type
        body = managed_default_return_expression(method.return_type)
        return f"""        public virtual {return_type} {method.cs_name}({args})
        {{
{body}
        }}
"""
    native_args = ([] if method.is_static else ["NativePtr"]) + [managed_native_arg_expression(arg) for arg in method.args]
    if method.is_vararg:
        native_args.append("varargs")
    call = f"NativeCalls.Godot{method.cs_class_name}{method.icall_suffix}(" + ", ".join(native_args) + ")"
    return_type = method.return_type.managed_type
    body = managed_return_expression(method, call)
    static_modifier = "static " if method.is_static else ""
    return f"""        public {static_modifier}{return_type} {method.cs_name}({args})
        {{
{body}
        }}
"""


def generate_node_name_property():
    return """        public StringName Name
        {
            get { return new StringName(NativeCalls.GodotNodeGetName(NativePtr)); }
            set { NativeCalls.GodotNodeSetName(NativePtr, value.ToString()); }
        }
"""


def generate_node2d_vector2_property(property_name, getter, setter):
    return f"""        public Vector2 {property_name}
        {{
            get {{ return NativeCalls.GodotNode2D{getter}(NativePtr); }}
            set {{ NativeCalls.GodotNode2D{setter}(NativePtr, value); }}
        }}
"""


def generate_vector2_property(class_name, property_name, getter, setter):
    return f"""        public Vector2 {property_name}
        {{
            get {{ return NativeCalls.Godot{class_name}{getter}(NativePtr); }}
            set {{ NativeCalls.Godot{class_name}{setter}(NativePtr, value); }}
        }}
"""


def generate_bool_property(class_name, property_name, getter, setter):
    return f"""        public bool {property_name}
        {{
            get {{ return NativeCalls.Godot{class_name}{getter}(NativePtr); }}
            set {{ NativeCalls.Godot{class_name}{setter}(NativePtr, value); }}
        }}
"""


def generate_string_property(class_name, property_name, getter, setter):
    return f"""        public string {property_name}
        {{
            get {{ return NativeCalls.Godot{class_name}{getter}(NativePtr); }}
            set {{ NativeCalls.Godot{class_name}{setter}(NativePtr, value); }}
        }}
"""


def generate_builtin_wrappers(generated):
    write(
        generated / "Variant.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Explicit)]
        public partial struct Variant : IEquatable<Variant>
        {
        private const int OwnsNativePtrFlag = 1;

        [StructLayout(LayoutKind.Explicit)]
        private struct VariantUnion
        {
            [FieldOffset(0)]
            public bool Bool;

            [FieldOffset(0)]
            public long Int;

            [FieldOffset(0)]
            public double Float;

            [FieldOffset(0)]
            public string String;

            [FieldOffset(0)]
            public long Rid;

            [FieldOffset(0)]
            public IntPtr NativePtr;

            [FieldOffset(0)]
            public Vector2 Vector2;

            [FieldOffset(0)]
            public Vector2i Vector2i;

            [FieldOffset(0)]
            public Vector3 Vector3;

            [FieldOffset(0)]
            public Vector3i Vector3i;

            [FieldOffset(0)]
            public Vector4 Vector4;

            [FieldOffset(0)]
            public Vector4i Vector4i;

            [FieldOffset(0)]
            public Color Color;

            [FieldOffset(0)]
            public Rect2 Rect2;

            [FieldOffset(0)]
            public Rect2i Rect2i;

            [FieldOffset(0)]
            public Transform2D Transform2D;

            [FieldOffset(0)]
            public Aabb Aabb;

            [FieldOffset(0)]
            public Quaternion Quaternion;

            [FieldOffset(0)]
            public Basis Basis;

            [FieldOffset(0)]
            public Transform3D Transform3D;

            [FieldOffset(0)]
            public Plane Plane;

            [FieldOffset(0)]
            public Projection Projection;
        }

        [FieldOffset(0)]
        private Type variantType;

        [FieldOffset(4)]
        private int flags;

        [FieldOffset(8)]
        private VariantUnion data;

        public Variant(bool value)
        {
            variantType = Type.Bool_;
            flags = 0;
            data = default(VariantUnion);
            data.Bool = value;
        }

        public Variant(int value)
            : this((long)value)
        {
        }

        public Variant(long value)
        {
            variantType = Type.Int_;
            flags = 0;
            data = default(VariantUnion);
            data.Int = value;
        }

        public Variant(float value)
            : this((double)value)
        {
        }

        public Variant(double value)
        {
            variantType = Type.Float_;
            flags = 0;
            data = default(VariantUnion);
            data.Float = value;
        }

        public Variant(string value)
        {
            variantType = Type.String_;
            flags = 0;
            data = default(VariantUnion);
            data.String = value ?? string.Empty;
        }

        public Variant(StringName value)
        {
            variantType = Type.StringName;
            flags = 0;
            data = default(VariantUnion);
            data.String = value.ToString();
        }

        public Variant(NodePath value)
        {
            variantType = Type.NodePath;
            flags = 0;
            data = default(VariantUnion);
            data.String = value.ToString();
        }

        public Variant(RID value)
        {
            variantType = Type.Rid;
            flags = 0;
            data = default(VariantUnion);
            data.Rid = value.GetId();
        }

        public Variant(GodotObject value)
        {
            variantType = Type.Object_;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(Array value)
        {
            variantType = Type.Array;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(Dictionary value)
        {
            variantType = Type.Dictionary;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(PackedByteArray value)
        {
            variantType = Type.PackedByteArray;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(PackedInt32Array value)
        {
            variantType = Type.PackedInt32Array;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(PackedInt64Array value)
        {
            variantType = Type.PackedInt64Array;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(PackedFloat32Array value)
        {
            variantType = Type.PackedFloat32Array;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(PackedFloat64Array value)
        {
            variantType = Type.PackedFloat64Array;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(PackedStringArray value)
        {
            variantType = Type.PackedStringArray;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(PackedVector2Array value)
        {
            variantType = Type.PackedVector2Array;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(PackedVector3Array value)
        {
            variantType = Type.PackedVector3Array;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(PackedColorArray value)
        {
            variantType = Type.PackedColorArray;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(Callable value)
        {
            variantType = Type.Callable;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(Signal value)
        {
            variantType = Type.Signal;
            flags = 0;
            data = default(VariantUnion);
            data.NativePtr = value != null ? value.NativePtr : IntPtr.Zero;
        }

        public Variant(Vector2 value)
        {
            variantType = Type.Vector2;
            flags = 0;
            data = default(VariantUnion);
            data.Vector2 = value;
        }

        public Variant(Vector2i value)
        {
            variantType = Type.Vector2i;
            flags = 0;
            data = default(VariantUnion);
            data.Vector2i = value;
        }

        public Variant(Vector3 value)
        {
            variantType = Type.Vector3;
            flags = 0;
            data = default(VariantUnion);
            data.Vector3 = value;
        }

        public Variant(Vector3i value)
        {
            variantType = Type.Vector3i;
            flags = 0;
            data = default(VariantUnion);
            data.Vector3i = value;
        }

        public Variant(Vector4 value)
        {
            variantType = Type.Vector4;
            flags = 0;
            data = default(VariantUnion);
            data.Vector4 = value;
        }

        public Variant(Vector4i value)
        {
            variantType = Type.Vector4i;
            flags = 0;
            data = default(VariantUnion);
            data.Vector4i = value;
        }

        public Variant(Projection value)
        {
            variantType = Type.Projection;
            flags = 0;
            data = default(VariantUnion);
            data.Projection = value;
        }

        public Variant(Color value)
        {
            variantType = Type.Color;
            flags = 0;
            data = default(VariantUnion);
            data.Color = value;
        }

        public Variant(Rect2 value)
        {
            variantType = Type.Rect2;
            flags = 0;
            data = default(VariantUnion);
            data.Rect2 = value;
        }

        public Variant(Rect2i value)
        {
            variantType = Type.Rect2i;
            flags = 0;
            data = default(VariantUnion);
            data.Rect2i = value;
        }

        public Variant(Transform2D value)
        {
            variantType = Type.Transform2d;
            flags = 0;
            data = default(VariantUnion);
            data.Transform2D = value;
        }

        public Variant(Aabb value)
        {
            variantType = Type.Aabb;
            flags = 0;
            data = default(VariantUnion);
            data.Aabb = value;
        }

        public Variant(Plane value)
        {
            variantType = Type.Plane;
            flags = 0;
            data = default(VariantUnion);
            data.Plane = value;
        }

        public Variant(Quaternion value)
        {
            variantType = Type.Quaternion;
            flags = 0;
            data = default(VariantUnion);
            data.Quaternion = value;
        }

        public Variant(Basis value)
        {
            variantType = Type.Basis;
            flags = 0;
            data = default(VariantUnion);
            data.Basis = value;
        }

        public Variant(Transform3D value)
        {
            variantType = Type.Transform3d;
            flags = 0;
            data = default(VariantUnion);
            data.Transform3D = value;
        }

        public Type VariantType
        {
            get { return variantType; }
        }

        public void Dispose()
        {
            if ((flags & OwnsNativePtrFlag) != 0 && data.NativePtr != IntPtr.Zero)
            {
                if (variantType == Type.Array || variantType == Type.Dictionary || variantType == Type.Callable || variantType == Type.Signal || variantType == Type.PackedByteArray || variantType == Type.PackedInt32Array || variantType == Type.PackedInt64Array || variantType == Type.PackedFloat32Array || variantType == Type.PackedFloat64Array || variantType == Type.PackedVector2Array || variantType == Type.PackedVector3Array || variantType == Type.PackedColorArray)
                {
                    NativeCalls.GodotOpaqueValueDestroy(data.NativePtr);
                }
                else if (variantType == Type.PackedStringArray)
                {
                    NativeCalls.GodotPackedStringArrayDestroy(data.NativePtr);
                }

                data.NativePtr = IntPtr.Zero;
                flags = 0;
            }
        }

        public bool AsBool()
        {
            return data.Bool;
        }

        public long AsInt64()
        {
            return data.Int;
        }

        public double AsDouble()
        {
            return data.Float;
        }

        public string AsString()
        {
            return data.String ?? string.Empty;
        }

        public StringName AsStringName()
        {
            return new StringName(data.String ?? string.Empty);
        }

        public NodePath AsNodePath()
        {
            return new NodePath(data.String ?? string.Empty);
        }

        public RID AsRID()
        {
            return new RID(data.Rid);
        }

        public T AsObject<T>() where T : GodotObject, new()
        {
            return GodotObject.CreateFromNative<T>(data.NativePtr);
        }

        public Array AsArray()
        {
            return Array.CreateFromNative(data.NativePtr, false);
        }

        public Dictionary AsDictionary()
        {
            return Dictionary.CreateFromNative(data.NativePtr, false);
        }

        public PackedByteArray AsPackedByteArray()
        {
            return PackedByteArray.CreateFromNative(data.NativePtr, false);
        }

        public PackedInt32Array AsPackedInt32Array()
        {
            return PackedInt32Array.CreateFromNative(data.NativePtr, false);
        }

        public PackedInt64Array AsPackedInt64Array()
        {
            return PackedInt64Array.CreateFromNative(data.NativePtr, false);
        }

        public PackedFloat32Array AsPackedFloat32Array()
        {
            return PackedFloat32Array.CreateFromNative(data.NativePtr, false);
        }

        public PackedFloat64Array AsPackedFloat64Array()
        {
            return PackedFloat64Array.CreateFromNative(data.NativePtr, false);
        }

        public PackedStringArray AsPackedStringArray()
        {
            return PackedStringArray.CreateFromNative(data.NativePtr, false);
        }

        public PackedVector2Array AsPackedVector2Array()
        {
            return PackedVector2Array.CreateFromNative(data.NativePtr, false);
        }

        public PackedVector3Array AsPackedVector3Array()
        {
            return PackedVector3Array.CreateFromNative(data.NativePtr, false);
        }

        public PackedColorArray AsPackedColorArray()
        {
            return PackedColorArray.CreateFromNative(data.NativePtr, false);
        }

        public Callable AsCallable()
        {
            return Callable.CreateFromNative(data.NativePtr, false);
        }

        public Signal AsSignal()
        {
            return Signal.CreateFromNative(data.NativePtr, false);
        }

        public Vector2 AsVector2()
        {
            return data.Vector2;
        }

        public Vector2i AsVector2i()
        {
            return data.Vector2i;
        }

        public Vector3 AsVector3()
        {
            return data.Vector3;
        }

        public Vector3i AsVector3i()
        {
            return data.Vector3i;
        }

        public Vector4 AsVector4()
        {
            return data.Vector4;
        }

        public Vector4i AsVector4i()
        {
            return data.Vector4i;
        }

        public Projection AsProjection()
        {
            return data.Projection;
        }

        public Color AsColor()
        {
            return data.Color;
        }

        public Rect2 AsRect2()
        {
            return data.Rect2;
        }

        public Rect2i AsRect2i()
        {
            return data.Rect2i;
        }

        public Transform2D AsTransform2D()
        {
            return data.Transform2D;
        }

        public Aabb AsAabb()
        {
            return data.Aabb;
        }

        public Plane AsPlane()
        {
            return data.Plane;
        }

        public Quaternion AsQuaternion()
        {
            return data.Quaternion;
        }

        public Basis AsBasis()
        {
            return data.Basis;
        }

        public Transform3D AsTransform3D()
        {
            return data.Transform3D;
        }

        public bool Equals(Variant other)
        {
            if (variantType != other.variantType)
            {
                return false;
            }

            switch (variantType)
            {
                case Type.Nil:
                    return true;
                case Type.Bool_:
                    return data.Bool == other.data.Bool;
                case Type.Int_:
                    return data.Int == other.data.Int;
                case Type.Float_:
                    return data.Float == other.data.Float;
                case Type.String_:
                case Type.StringName:
                case Type.NodePath:
                    return data.String == other.data.String;
                case Type.Rid:
                    return data.Rid == other.data.Rid;
                case Type.Object_:
                case Type.Array:
                case Type.Dictionary:
                case Type.Callable:
                case Type.Signal:
                case Type.PackedStringArray:
                case Type.PackedByteArray:
                case Type.PackedInt32Array:
                case Type.PackedInt64Array:
                case Type.PackedFloat32Array:
                case Type.PackedFloat64Array:
                case Type.PackedVector2Array:
                case Type.PackedVector3Array:
                case Type.PackedColorArray:
                    return data.NativePtr == other.data.NativePtr;
                case Type.Vector2:
                    return data.Vector2.Equals(other.data.Vector2);
                case Type.Vector2i:
                    return data.Vector2i.Equals(other.data.Vector2i);
                case Type.Vector3:
                    return data.Vector3.Equals(other.data.Vector3);
                case Type.Vector3i:
                    return data.Vector3i.Equals(other.data.Vector3i);
                case Type.Vector4:
                    return data.Vector4.Equals(other.data.Vector4);
                case Type.Vector4i:
                    return data.Vector4i.Equals(other.data.Vector4i);
                case Type.Projection:
                    return data.Projection.Equals(other.data.Projection);
                case Type.Color:
                    return data.Color.Equals(other.data.Color);
                case Type.Rect2:
                    return data.Rect2.Equals(other.data.Rect2);
                case Type.Rect2i:
                    return data.Rect2i.Equals(other.data.Rect2i);
                case Type.Transform2d:
                    return data.Transform2D.Equals(other.data.Transform2D);
                case Type.Aabb:
                    return data.Aabb.Equals(other.data.Aabb);
                case Type.Plane:
                    return data.Plane.Equals(other.data.Plane);
                case Type.Quaternion:
                    return data.Quaternion.Equals(other.data.Quaternion);
                case Type.Basis:
                    return data.Basis.Equals(other.data.Basis);
                case Type.Transform3d:
                    return data.Transform3D.Equals(other.data.Transform3D);
                default:
                    return false;
            }
        }

        public override bool Equals(object obj)
        {
            return obj is Variant && Equals((Variant)obj);
        }

        public override int GetHashCode()
        {
            return ToString().GetHashCode();
        }

        public override string ToString()
        {
            return NativeCalls.GodotVariantStringify(this);
        }
    }
}
""",
    )

    write(
        generated / "PackedStringArray.generated.cs",
        """// <auto-generated />
using System;

namespace Godot
{
    public partial class PackedStringArray : IDisposable
    {
        internal IntPtr NativePtr;
        private bool ownsNativePtr;

        public PackedStringArray()
            : this(NativeCalls.GodotPackedStringArrayCreate(), true)
        {
        }

        public PackedStringArray(string[] values)
            : this()
        {
            if (values == null)
            {
                return;
            }

            for (int i = 0; i < values.Length; ++i)
            {
                Add(values[i]);
            }
        }

        private PackedStringArray(IntPtr nativePtr, bool ownsNativePtr)
        {
            NativePtr = nativePtr;
            this.ownsNativePtr = ownsNativePtr;
        }

        internal static PackedStringArray CreateFromNative(IntPtr nativePtr)
        {
            return CreateFromNative(nativePtr, true);
        }

        internal static PackedStringArray CreateFromNative(IntPtr nativePtr, bool ownsNativePtr)
        {
            return nativePtr != IntPtr.Zero ? new PackedStringArray(nativePtr, ownsNativePtr) : null;
        }

        ~PackedStringArray()
        {
            Dispose(false);
        }

        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
        }

        private void Dispose(bool disposing)
        {
            if (ownsNativePtr && NativePtr != IntPtr.Zero)
            {
                NativeCalls.GodotPackedStringArrayDestroy(NativePtr);
                NativePtr = IntPtr.Zero;
                ownsNativePtr = false;
            }
        }

        public int Count
        {
            get { return NativePtr != IntPtr.Zero ? NativeCalls.GodotPackedStringArraySize(NativePtr) : 0; }
        }

        public string this[int index]
        {
            get { return NativeCalls.GodotPackedStringArrayGet(NativePtr, index); }
        }

        public void Add(string value)
        {
            NativeCalls.GodotPackedStringArrayAppend(NativePtr, value);
        }

        public string[] ToArray()
        {
            string[] values = new string[Count];
            for (int i = 0; i < values.Length; ++i)
            {
                values[i] = this[i];
            }
            return values;
        }
    }
}
""",
    )

    opaque_wrappers = sorted(PACKED_ARRAY_TYPES | OPAQUE_VARIANT_TYPES | OPAQUE_VALUE_TYPES | {"GodotArray"})
    for wrapper_name in opaque_wrappers:
        destroy_call = "NativeCalls.GodotOpaqueValueDestroy"
        create_call = {"Array": "GodotArrayCreate", "Dictionary": "GodotDictionaryCreate"}.get(wrapper_name)
        public_constructor = (
            f"""\n        public {wrapper_name}()\n            : this(NativeCalls.{create_call}(), true)\n        {{\n        }}\n"""
            if create_call is not None
            else ""
        )
        collection_methods = ""
        extra_constructor = ""
        if wrapper_name == "Callable":
            extra_constructor = """

        public Callable(GodotObject target, StringName method)
            : this(NativeCalls.GodotCallableCreate(target != null ? target.NativePtr : IntPtr.Zero, method.ToString()), true)
        {
        }

        public static Callable From(Action action)
        {
            long delegateId = CallableDelegateRegistry.Register(args => { action(); return new Variant(); });
            return new Callable(NativeCalls.GodotCallableCreateDelegate(delegateId), true, delegateId);
        }

        public static Callable From(Func<Variant> function)
        {
            long delegateId = CallableDelegateRegistry.Register(args => function());
            return new Callable(NativeCalls.GodotCallableCreateDelegate(delegateId), true, delegateId);
        }

        public static Callable From<T>(Action<T> action)
        {
            long delegateId = CallableDelegateRegistry.Register(args => { action(CallableDelegateRegistry.ConvertArgument<T>(args, 0)); return new Variant(); });
            return new Callable(NativeCalls.GodotCallableCreateDelegate(delegateId), true, delegateId);
        }

        public static Callable From<T>(Func<T, Variant> function)
        {
            long delegateId = CallableDelegateRegistry.Register(args => function(CallableDelegateRegistry.ConvertArgument<T>(args, 0)));
            return new Callable(NativeCalls.GodotCallableCreateDelegate(delegateId), true, delegateId);
        }
"""
            collection_methods = """
        public bool IsValid()
        {
            return NativeCalls.GodotCallableIsValid(NativePtr);
        }

        public StringName GetMethod()
        {
            return new StringName(NativeCalls.GodotCallableGetMethod(NativePtr));
        }

        public Variant Call(params Variant[] varargs)
        {
            return NativeCalls.GodotCallableCall(NativePtr, varargs);
        }

        public Callable Bind(params Variant[] varargs)
        {
            return CreateFromNative(NativeCalls.GodotCallableBind(NativePtr, varargs));
        }
"""
        elif wrapper_name == "Signal":
            extra_constructor = """

        public Signal(GodotObject target, StringName signal)
            : this(NativeCalls.GodotSignalCreate(target != null ? target.NativePtr : IntPtr.Zero, signal.ToString()), true)
        {
        }
"""
            collection_methods = """
        public bool IsNull()
        {
            return NativeCalls.GodotSignalIsNull(NativePtr);
        }

        public StringName GetName()
        {
            return new StringName(NativeCalls.GodotSignalGetName(NativePtr));
        }

        public Error Connect(Callable callable, int flags)
        {
            return (Error)NativeCalls.GodotSignalConnect(NativePtr, callable != null ? callable.NativePtr : IntPtr.Zero, flags);
        }

        public void Emit(params Variant[] varargs)
        {
            NativeCalls.GodotSignalEmit(NativePtr, varargs);
        }
"""

        elif wrapper_name in PACKED_ARRAY_INFOS:
            element_type = PACKED_ARRAY_INFOS[wrapper_name]["cs"]
            public_constructor = f"""
        public {wrapper_name}()
            : this(NativeCalls.Godot{wrapper_name}Create(), true)
        {{
        }}
"""
            collection_methods = f"""
        public int Count
        {{
            get {{ return NativePtr != IntPtr.Zero ? NativeCalls.Godot{wrapper_name}Size(NativePtr) : 0; }}
        }}

        public {element_type} this[int index]
        {{
            get {{ return NativeCalls.Godot{wrapper_name}Get(NativePtr, index); }}
            set {{ NativeCalls.Godot{wrapper_name}Set(NativePtr, index, value); }}
        }}

        public void Add({element_type} value)
        {{
            NativeCalls.Godot{wrapper_name}Add(NativePtr, value);
        }}

        public void Clear()
        {{
            NativeCalls.Godot{wrapper_name}Clear(NativePtr);
        }}

        public {element_type}[] ToArray()
        {{
            {element_type}[] values = new {element_type}[Count];
            for (int i = 0; i < values.Length; ++i)
            {{
                values[i] = this[i];
            }}
            return values;
        }}
"""
        if wrapper_name == "Array" or wrapper_name == "GodotArray":
            collection_methods = """
        public int Count
        {
            get { return NativePtr != IntPtr.Zero ? NativeCalls.GodotArraySize(NativePtr) : 0; }
        }

        public Variant this[int index]
        {
            get { return NativeCalls.GodotArrayGet(NativePtr, index); }
            set { NativeCalls.GodotArraySet(NativePtr, index, value); }
        }

        public void Add(Variant value)
        {
            NativeCalls.GodotArrayAdd(NativePtr, value);
        }

        public void Insert(int index, Variant value)
        {
            NativeCalls.GodotArrayInsert(NativePtr, index, value);
        }

        public void RemoveAt(int index)
        {
            NativeCalls.GodotArrayRemoveAt(NativePtr, index);
        }

        public void Clear()
        {
            NativeCalls.GodotArrayClear(NativePtr);
        }

        public bool Contains(Variant value)
        {
            return NativeCalls.GodotArrayContains(NativePtr, value);
        }

        public int IndexOf(Variant value)
        {
            return NativeCalls.GodotArrayIndexOf(NativePtr, value);
        }

        public Variant[] ToArray()
        {
            Variant[] values = new Variant[Count];
            for (int i = 0; i < values.Length; ++i)
            {
                values[i] = this[i];
            }
            return values;
        }

        public IEnumerator<Variant> GetEnumerator()
        {
            for (int i = 0; i < Count; ++i)
            {
                yield return this[i];
            }
        }

        IEnumerator IEnumerable.GetEnumerator()
        {
            return GetEnumerator();
        }
"""
        elif wrapper_name == "Dictionary":
            collection_methods = """
        public int Count
        {
            get { return NativePtr != IntPtr.Zero ? NativeCalls.GodotDictionarySize(NativePtr) : 0; }
        }

        public Variant this[Variant key]
        {
            get { return NativeCalls.GodotDictionaryGet(NativePtr, key); }
            set { NativeCalls.GodotDictionarySet(NativePtr, key, value); }
        }

        public bool ContainsKey(Variant key)
        {
            return NativeCalls.GodotDictionaryContainsKey(NativePtr, key);
        }

        public bool Remove(Variant key)
        {
            return NativeCalls.GodotDictionaryRemove(NativePtr, key);
        }

        public void Clear()
        {
            NativeCalls.GodotDictionaryClear(NativePtr);
        }

        public Array Keys
        {
            get { return Array.CreateFromNative(NativeCalls.GodotDictionaryKeys(NativePtr)); }
        }

        public Array Values
        {
            get { return Array.CreateFromNative(NativeCalls.GodotDictionaryValues(NativePtr)); }
        }

        public IEnumerator<KeyValuePair<Variant, Variant>> GetEnumerator()
        {
            Array keys = Keys;
            for (int i = 0; i < keys.Count; ++i)
            {
                Variant key = keys[i];
                yield return new KeyValuePair<Variant, Variant>(key, this[key]);
            }
            keys.Dispose();
        }

        IEnumerator IEnumerable.GetEnumerator()
        {
            return GetEnumerator();
        }
"""
        write(
            generated / f"{wrapper_name}.generated.cs",
            f"""// <auto-generated />
using System;
using System.Collections;
using System.Collections.Generic;

namespace Godot
{{
    public partial class {wrapper_name} : IDisposable{', IEnumerable<Variant>' if wrapper_name == 'Array' or wrapper_name == 'GodotArray' else ', IEnumerable<KeyValuePair<Variant, Variant>>' if wrapper_name == 'Dictionary' else ''}
    {{
        internal IntPtr NativePtr;
        private bool ownsNativePtr;
        private long delegateId;

        internal static {wrapper_name} CreateFromNative(IntPtr nativePtr)
        {{
            return nativePtr != IntPtr.Zero ? new {wrapper_name}(nativePtr, true) : null;
        }}

        internal static {wrapper_name} CreateFromNative(IntPtr nativePtr, bool ownsNativePtr)
        {{
            return nativePtr != IntPtr.Zero ? new {wrapper_name}(nativePtr, ownsNativePtr) : null;
        }}
{public_constructor}{extra_constructor}

        private {wrapper_name}(IntPtr nativePtr, bool ownsNativePtr)
            : this(nativePtr, ownsNativePtr, 0)
        {{
        }}

        private {wrapper_name}(IntPtr nativePtr, bool ownsNativePtr, long delegateId)
        {{
            NativePtr = nativePtr;
            this.ownsNativePtr = ownsNativePtr;
            this.delegateId = delegateId;
        }}

        ~{wrapper_name}()
        {{
            Dispose(false);
        }}

        public void Dispose()
        {{
            Dispose(true);
            GC.SuppressFinalize(this);
        }}

        private void Dispose(bool disposing)
        {{
            if (ownsNativePtr && NativePtr != IntPtr.Zero)
            {{
                {destroy_call}(NativePtr);
                if (delegateId != 0)
                {{
                    CallableDelegateRegistry.Unregister(delegateId);
                    delegateId = 0;
                }}
                NativePtr = IntPtr.Zero;
                ownsNativePtr = false;
            }}
        }}
{collection_methods}
    }}
}}
""",
        )

    write(
        generated / "StringName.generated.cs",
        """// <auto-generated />
using System;

namespace Godot
{
    public struct StringName : IEquatable<StringName>
    {
        private readonly string value;

        public StringName(string value)
        {
            this.value = value ?? string.Empty;
        }

        public bool Equals(StringName other)
        {
            return ToString() == other.ToString();
        }

        public override bool Equals(object obj)
        {
            return obj is StringName && Equals((StringName)obj);
        }

        public override int GetHashCode()
        {
            return ToString().GetHashCode();
        }

        public override string ToString()
        {
            return value ?? string.Empty;
        }

        public static implicit operator StringName(string value)
        {
            return new StringName(value);
        }

        public static implicit operator string(StringName value)
        {
            return value.ToString();
        }
    }
}
""",
    )

    write(
        generated / "Vector2.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Vector2 : IEquatable<Vector2>
    {
        public float X;
        public float Y;

        public Vector2(float x, float y)
        {
            X = x;
            Y = y;
        }

        public bool Equals(Vector2 other)
        {
            return X == other.X && Y == other.Y;
        }

        public override bool Equals(object obj)
        {
            return obj is Vector2 && Equals((Vector2)obj);
        }

        public override int GetHashCode()
        {
            return X.GetHashCode() ^ Y.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + X.ToString() + ", " + Y.ToString() + ")";
        }

        public static Vector2 One
        {
            get { return new Vector2(1.0f, 1.0f); }
        }

        public static Vector2 Zero
        {
            get { return new Vector2(0.0f, 0.0f); }
        }
    }
}
""",
    )

    write(
        generated / "Vector2i.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Vector2i : IEquatable<Vector2i>
    {
        public int X;
        public int Y;

        public Vector2i(int x, int y)
        {
            X = x;
            Y = y;
        }

        public bool Equals(Vector2i other)
        {
            return X == other.X && Y == other.Y;
        }

        public override bool Equals(object obj)
        {
            return obj is Vector2i && Equals((Vector2i)obj);
        }

        public override int GetHashCode()
        {
            return X.GetHashCode() ^ Y.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + X.ToString() + ", " + Y.ToString() + ")";
        }

        public static Vector2i One
        {
            get { return new Vector2i(1, 1); }
        }

        public static Vector2i Zero
        {
            get { return new Vector2i(0, 0); }
        }
    }
}
""",
    )

    write(
        generated / "Vector3.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Vector3 : IEquatable<Vector3>
    {
        public float X;
        public float Y;
        public float Z;

        public Vector3(float x, float y, float z)
        {
            X = x;
            Y = y;
            Z = z;
        }

        public bool Equals(Vector3 other)
        {
            return X == other.X && Y == other.Y && Z == other.Z;
        }

        public override bool Equals(object obj)
        {
            return obj is Vector3 && Equals((Vector3)obj);
        }

        public override int GetHashCode()
        {
            return X.GetHashCode() ^ Y.GetHashCode() ^ Z.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + X.ToString() + ", " + Y.ToString() + ", " + Z.ToString() + ")";
        }

        public static Vector3 One
        {
            get { return new Vector3(1.0f, 1.0f, 1.0f); }
        }

        public static Vector3 Zero
        {
            get { return new Vector3(0.0f, 0.0f, 0.0f); }
        }
    }
}
""",
    )

    write(
        generated / "Vector3i.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Vector3i : IEquatable<Vector3i>
    {
        public int X;
        public int Y;
        public int Z;

        public Vector3i(int x, int y, int z)
        {
            X = x;
            Y = y;
            Z = z;
        }

        public bool Equals(Vector3i other)
        {
            return X == other.X && Y == other.Y && Z == other.Z;
        }

        public override bool Equals(object obj)
        {
            return obj is Vector3i && Equals((Vector3i)obj);
        }

        public override int GetHashCode()
        {
            return X.GetHashCode() ^ Y.GetHashCode() ^ Z.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + X.ToString() + ", " + Y.ToString() + ", " + Z.ToString() + ")";
        }
    }
}
""",
    )

    write(
        generated / "Rect2.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Rect2 : IEquatable<Rect2>
    {
        public Vector2 Position;
        public Vector2 Size;

        public Rect2(Vector2 position, Vector2 size)
        {
            Position = position;
            Size = size;
        }

        public Rect2(float x, float y, float width, float height)
        {
            Position = new Vector2(x, y);
            Size = new Vector2(width, height);
        }

        public bool Equals(Rect2 other)
        {
            return Position.Equals(other.Position) && Size.Equals(other.Size);
        }

        public override bool Equals(object obj)
        {
            return obj is Rect2 && Equals((Rect2)obj);
        }

        public override int GetHashCode()
        {
            return Position.GetHashCode() ^ Size.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + Position.ToString() + ", " + Size.ToString() + ")";
        }
    }
}
""",
    )

    write(
        generated / "Rect2i.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Rect2i : IEquatable<Rect2i>
    {
        public Vector2i Position;
        public Vector2i Size;

        public Rect2i(Vector2i position, Vector2i size)
        {
            Position = position;
            Size = size;
        }

        public Rect2i(int x, int y, int width, int height)
        {
            Position = new Vector2i(x, y);
            Size = new Vector2i(width, height);
        }

        public bool Equals(Rect2i other)
        {
            return Position.Equals(other.Position) && Size.Equals(other.Size);
        }

        public override bool Equals(object obj)
        {
            return obj is Rect2i && Equals((Rect2i)obj);
        }

        public override int GetHashCode()
        {
            return Position.GetHashCode() ^ Size.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + Position.ToString() + ", " + Size.ToString() + ")";
        }
    }
}
""",
    )

    write(
        generated / "Transform2D.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Transform2D : IEquatable<Transform2D>
    {
        public Vector2 X;
        public Vector2 Y;
        public Vector2 Origin;

        public Transform2D(Vector2 x, Vector2 y, Vector2 origin)
        {
            X = x;
            Y = y;
            Origin = origin;
        }

        public bool Equals(Transform2D other)
        {
            return X.Equals(other.X) && Y.Equals(other.Y) && Origin.Equals(other.Origin);
        }

        public override bool Equals(object obj)
        {
            return obj is Transform2D && Equals((Transform2D)obj);
        }

        public override int GetHashCode()
        {
            return X.GetHashCode() ^ Y.GetHashCode() ^ Origin.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + X.ToString() + ", " + Y.ToString() + ", " + Origin.ToString() + ")";
        }

        public static Transform2D Identity
        {
            get { return new Transform2D(new Vector2(1.0f, 0.0f), new Vector2(0.0f, 1.0f), Vector2.Zero); }
        }
    }
}
""",
    )

    write(
        generated / "Aabb.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Aabb : IEquatable<Aabb>
    {
        public Vector3 Position;
        public Vector3 Size;

        public Aabb(Vector3 position, Vector3 size)
        {
            Position = position;
            Size = size;
        }

        public bool Equals(Aabb other)
        {
            return Position.Equals(other.Position) && Size.Equals(other.Size);
        }

        public override bool Equals(object obj)
        {
            return obj is Aabb && Equals((Aabb)obj);
        }

        public override int GetHashCode()
        {
            return Position.GetHashCode() ^ Size.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + Position.ToString() + ", " + Size.ToString() + ")";
        }
    }
}
""",
    )

    write(
        generated / "Quaternion.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Quaternion : IEquatable<Quaternion>
    {
        public float X;
        public float Y;
        public float Z;
        public float W;

        public Quaternion(float x, float y, float z, float w)
        {
            X = x;
            Y = y;
            Z = z;
            W = w;
        }

        public bool Equals(Quaternion other)
        {
            return X == other.X && Y == other.Y && Z == other.Z && W == other.W;
        }

        public override bool Equals(object obj)
        {
            return obj is Quaternion && Equals((Quaternion)obj);
        }

        public override int GetHashCode()
        {
            return X.GetHashCode() ^ Y.GetHashCode() ^ Z.GetHashCode() ^ W.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + X.ToString() + ", " + Y.ToString() + ", " + Z.ToString() + ", " + W.ToString() + ")";
        }

        public static Quaternion Identity
        {
            get { return new Quaternion(0.0f, 0.0f, 0.0f, 1.0f); }
        }
    }
}
""",
    )

    write(
        generated / "Basis.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Basis : IEquatable<Basis>
    {
        public Vector3 X;
        public Vector3 Y;
        public Vector3 Z;

        public Basis(Vector3 x, Vector3 y, Vector3 z)
        {
            X = x;
            Y = y;
            Z = z;
        }

        public bool Equals(Basis other)
        {
            return X.Equals(other.X) && Y.Equals(other.Y) && Z.Equals(other.Z);
        }

        public override bool Equals(object obj)
        {
            return obj is Basis && Equals((Basis)obj);
        }

        public override int GetHashCode()
        {
            return X.GetHashCode() ^ Y.GetHashCode() ^ Z.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + X.ToString() + ", " + Y.ToString() + ", " + Z.ToString() + ")";
        }

        public static Basis Identity
        {
            get { return new Basis(new Vector3(1.0f, 0.0f, 0.0f), new Vector3(0.0f, 1.0f, 0.0f), new Vector3(0.0f, 0.0f, 1.0f)); }
        }
    }
}
""",
    )

    write(
        generated / "Transform3D.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Transform3D : IEquatable<Transform3D>
    {
        public Basis Basis;
        public Vector3 Origin;

        public Transform3D(Basis basis, Vector3 origin)
        {
            Basis = basis;
            Origin = origin;
        }

        public bool Equals(Transform3D other)
        {
            return Basis.Equals(other.Basis) && Origin.Equals(other.Origin);
        }

        public override bool Equals(object obj)
        {
            return obj is Transform3D && Equals((Transform3D)obj);
        }

        public override int GetHashCode()
        {
            return Basis.GetHashCode() ^ Origin.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + Basis.ToString() + ", " + Origin.ToString() + ")";
        }

        public static Transform3D Identity
        {
            get { return new Transform3D(Basis.Identity, Vector3.Zero); }
        }
    }
}
""",
    )

    write(
        generated / "Vector4.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Vector4 : IEquatable<Vector4>
    {
        public float X;
        public float Y;
        public float Z;
        public float W;

        public Vector4(float x, float y, float z, float w)
        {
            X = x;
            Y = y;
            Z = z;
            W = w;
        }

        public bool Equals(Vector4 other)
        {
            return X == other.X && Y == other.Y && Z == other.Z && W == other.W;
        }

        public override bool Equals(object obj)
        {
            return obj is Vector4 && Equals((Vector4)obj);
        }

        public override int GetHashCode()
        {
            return X.GetHashCode() ^ Y.GetHashCode() ^ Z.GetHashCode() ^ W.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + X.ToString() + ", " + Y.ToString() + ", " + Z.ToString() + ", " + W.ToString() + ")";
        }
    }
}
""",
    )

    write(
        generated / "Vector4i.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Vector4i : IEquatable<Vector4i>
    {
        public int X;
        public int Y;
        public int Z;
        public int W;

        public Vector4i(int x, int y, int z, int w)
        {
            X = x;
            Y = y;
            Z = z;
            W = w;
        }

        public bool Equals(Vector4i other)
        {
            return X == other.X && Y == other.Y && Z == other.Z && W == other.W;
        }

        public override bool Equals(object obj)
        {
            return obj is Vector4i && Equals((Vector4i)obj);
        }

        public override int GetHashCode()
        {
            return X.GetHashCode() ^ Y.GetHashCode() ^ Z.GetHashCode() ^ W.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + X.ToString() + ", " + Y.ToString() + ", " + Z.ToString() + ", " + W.ToString() + ")";
        }
    }
}
""",
    )

    write(
        generated / "Plane.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Plane : IEquatable<Plane>
    {
        public Vector3 Normal;
        public float D;

        public Plane(Vector3 normal, float d)
        {
            Normal = normal;
            D = d;
        }

        public bool Equals(Plane other)
        {
            return Normal.Equals(other.Normal) && D == other.D;
        }

        public override bool Equals(object obj)
        {
            return obj is Plane && Equals((Plane)obj);
        }

        public override int GetHashCode()
        {
            return Normal.GetHashCode() ^ D.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + Normal.ToString() + ", " + D.ToString() + ")";
        }
    }
}
""",
    )

    write(
        generated / "Projection.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Projection : IEquatable<Projection>
    {
        public Vector4 X;
        public Vector4 Y;
        public Vector4 Z;
        public Vector4 W;

        public Projection(Vector4 x, Vector4 y, Vector4 z, Vector4 w)
        {
            X = x;
            Y = y;
            Z = z;
            W = w;
        }

        public bool Equals(Projection other)
        {
            return X.Equals(other.X) && Y.Equals(other.Y) && Z.Equals(other.Z) && W.Equals(other.W);
        }

        public override bool Equals(object obj)
        {
            return obj is Projection && Equals((Projection)obj);
        }

        public override int GetHashCode()
        {
            return X.GetHashCode() ^ Y.GetHashCode() ^ Z.GetHashCode() ^ W.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + X.ToString() + ", " + Y.ToString() + ", " + Z.ToString() + ", " + W.ToString() + ")";
        }
    }
}
""",
    )

    write(
        generated / "Color.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public partial struct Color : IEquatable<Color>
    {
        public float R;
        public float G;
        public float B;
        public float A;

        public Color(float r, float g, float b, float a)
        {
            R = r;
            G = g;
            B = b;
            A = a;
        }

        public bool Equals(Color other)
        {
            return R == other.R && G == other.G && B == other.B && A == other.A;
        }

        public override bool Equals(object obj)
        {
            return obj is Color && Equals((Color)obj);
        }

        public override int GetHashCode()
        {
            return R.GetHashCode() ^ G.GetHashCode() ^ B.GetHashCode() ^ A.GetHashCode();
        }

        public override string ToString()
        {
            return "(" + R.ToString() + ", " + G.ToString() + ", " + B.ToString() + ", " + A.ToString() + ")";
        }

        public static Color White
        {
            get { return new Color(1.0f, 1.0f, 1.0f, 1.0f); }
        }

        public static Color Transparent
        {
            get { return new Color(0.0f, 0.0f, 0.0f, 0.0f); }
        }
    }
}
""",
    )

    write(
        generated / "RID.generated.cs",
        """// <auto-generated />
using System;
using System.Runtime.InteropServices;

namespace Godot
{
    [StructLayout(LayoutKind.Sequential)]
    public struct RID : IEquatable<RID>
    {
        private readonly long id;

        public RID(long id)
        {
            this.id = id;
        }

        public bool IsValid()
        {
            return id != 0;
        }

        public long GetId()
        {
            return id;
        }

        public bool Equals(RID other)
        {
            return id == other.id;
        }

        public override bool Equals(object obj)
        {
            return obj is RID && Equals((RID)obj);
        }

        public override int GetHashCode()
        {
            return id.GetHashCode();
        }

        public override string ToString()
        {
            return id.ToString();
        }
    }
}
""",
    )

    write(
        generated / "NodePath.generated.cs",
        """// <auto-generated />
using System;

namespace Godot
{
    public struct NodePath : IEquatable<NodePath>
    {
        private readonly string value;

        public NodePath(string value)
        {
            this.value = value ?? string.Empty;
        }

        public bool Equals(NodePath other)
        {
            return ToString() == other.ToString();
        }

        public override bool Equals(object obj)
        {
            return obj is NodePath && Equals((NodePath)obj);
        }

        public override int GetHashCode()
        {
            return ToString().GetHashCode();
        }

        public override string ToString()
        {
            return value ?? string.Empty;
        }

        public static implicit operator NodePath(string value)
        {
            return new NodePath(value);
        }

        public static implicit operator string(NodePath value)
        {
            return value.ToString();
        }
    }
}
""",
    )


def screaming_enum_prefix(enum_name):
    result = []
    for char in enum_name:
        if char.isupper() and result:
            result.append("_")
        result.append(char.upper())
    return "".join(result)


def enum_member_name(enum_name, value_name):
    prefix = screaming_enum_prefix(enum_name)
    short_name = value_name
    if short_name.startswith(prefix + "_"):
        short_name = short_name[len(prefix) + 1 :]
    if short_name.startswith("FLAG_"):
        short_name = short_name[5:]
    return pascal_name(short_name.lower())


def generate_enum_declarations(class_entry):
    declarations = []
    seen_enum_names = set()
    for enum_entry in class_entry.get("enums", []):
        enum_name = cs_identifier(enum_entry["name"], "GodotEnum")
        if enum_name in seen_enum_names:
            continue
        seen_enum_names.add(enum_name)
        if enum_entry.get("is_bitfield"):
            declarations.append("        [Flags]")
            declarations.append(f"        public enum {enum_name} : long")
        else:
            declarations.append(f"        public enum {enum_name}")
        declarations.append("        {")
        seen_value_names = set()
        for value in enum_entry.get("values", []):
            member_name = enum_member_name(enum_entry["name"], value["name"])
            if member_name in seen_value_names:
                member_name = f"{member_name}_{value['value']}"
            seen_value_names.add(member_name)
            declarations.append(f"            {member_name} = {value['value']},")
        declarations.append("        }")
    return "\n".join(declarations)


def generate_standalone_nested_enum_declarations(type_name, enums):
    lines = [f"    public partial struct {cs_identifier(type_name, 'GodotBuiltin')}", "    {"]
    seen_enum_names = set()
    for enum_entry in enums:
        enum_name = cs_identifier(enum_entry["name"], "GodotEnum")
        if enum_name in seen_enum_names:
            continue
        seen_enum_names.add(enum_name)
        if enum_entry.get("is_bitfield"):
            lines.append("        [Flags]")
            lines.append(f"        public enum {enum_name} : long")
        else:
            lines.append(f"        public enum {enum_name}")
        lines.append("        {")
        seen_value_names = set()
        for value in enum_entry.get("values", []):
            member_name = enum_member_name(enum_entry["name"], value["name"])
            if member_name in seen_value_names:
                member_name = f"{member_name}_{value['value']}"
            seen_value_names.add(member_name)
            lines.append(f"            {member_name} = {value['value']},")
        lines.append("        }")
    lines.append("    }")
    return lines


def generate_builtin_enums(builtin_classes, generated):
    lines = ["// <auto-generated />", "using System;", "", "namespace Godot", "{"]
    for builtin_class in builtin_classes:
        enums = builtin_class.get("enums", [])
        if not enums:
            continue
        lines.extend(generate_standalone_nested_enum_declarations(builtin_class["name"], enums))
    lines.extend(["}", ""])
    write(generated / "BuiltinEnums.generated.cs", "\n".join(lines))


def generate_global_enums(global_enums, generated):
    lines = ["// <auto-generated />", "using System;", "", "namespace Godot", "{"]
    nested_enums = {}
    for enum_entry in global_enums:
        enum_name = cs_identifier(enum_entry["name"], "GodotEnum")
        if "." in enum_entry["name"]:
            container_name, nested_name = enum_entry["name"].split(".", 1)
            nested_entry = dict(enum_entry)
            nested_entry["name"] = nested_name
            nested_enums.setdefault(container_name, []).append(nested_entry)
            continue
        if enum_entry.get("is_bitfield"):
            lines.append("    [Flags]")
            lines.append(f"    public enum {enum_name} : long")
        else:
            lines.append(f"    public enum {enum_name}")
        lines.append("    {")
        seen_value_names = set()
        for value in enum_entry.get("values", []):
            member_name = enum_member_name(enum_entry["name"], value["name"])
            if member_name in seen_value_names:
                member_name = f"{member_name}_{value['value']}"
            seen_value_names.add(member_name)
            lines.append(f"        {member_name} = {value['value']},")
        lines.append("    }")
    for container_name, enums in nested_enums.items():
        lines.extend(generate_standalone_nested_enum_declarations(container_name, enums))
    lines.extend(["}", ""])
    write(generated / "GlobalEnums.generated.cs", "\n".join(lines))


def generate_managed(classes, class_order, global_enums, builtin_classes, methods, managed_dir):
    generated = managed_dir / "Generated"
    generated.mkdir(parents=True, exist_ok=True)
    for stale_file in generated.glob("*.generated.cs"):
        stale_file.unlink()
    generate_builtin_wrappers(generated)
    generate_builtin_enums(builtin_classes, generated)
    generate_global_enums(global_enums, generated)
    by_class = {name: [] for name in class_order}
    for method in methods:
        by_class[method.class_name].append(method)

    for class_name in class_order:
        cs_name = cs_class_name(class_name)
        lines = ["// <auto-generated />", "using System;", "", "namespace Godot", "{", f"    public partial class {cs_name}{managed_base_clause(class_name, classes)}", "    {"]
        enum_declarations = generate_enum_declarations(classes[class_name])
        if enum_declarations:
            lines.append(enum_declarations)
        if class_name == "Node":
            lines.append(generate_node_name_property().rstrip())
        if class_name == "Node2D":
            lines.append(generate_node2d_vector2_property("Position", "GetPosition", "SetPosition").rstrip())
            lines.append(generate_node2d_vector2_property("GlobalPosition", "GetGlobalPosition", "SetGlobalPosition").rstrip())
            lines.append(generate_node2d_vector2_property("Scale", "GetScale", "SetScale").rstrip())
        if class_name == "Control":
            lines.append(generate_vector2_property("Control", "Position", "GetPosition", "SetPosition").rstrip())
            lines.append(generate_vector2_property("Control", "Size", "GetSize", "SetSize").rstrip())
        if class_name == "Label":
            lines.append(generate_string_property("Label", "Text", "GetText", "SetText").rstrip())
        if class_name == "Sprite2D":
            lines.append(generate_bool_property("Sprite2D", "Centered", "IsCentered", "SetCentered").rstrip())
            lines.append(generate_vector2_property("Sprite2D", "Offset", "GetOffset", "SetOffset").rstrip())
            lines.append(generate_bool_property("Sprite2D", "FlipH", "IsFlippedH", "SetFlipH").rstrip())
            lines.append(generate_bool_property("Sprite2D", "FlipV", "IsFlippedV", "SetFlipV").rstrip())
        for method in by_class[class_name]:
            generated_method = generate_managed_method(method)
            if generated_method:
                lines.append(generated_method.rstrip())
        lines.extend(["    }", "}", ""])
        write(generated / f"{cs_name}.generated.cs", "\n".join(lines))

    native_call_lines = [
        "// <auto-generated />",
        "using System;",
        "using System.Runtime.CompilerServices;",
        "",
        "namespace Godot",
        "{",
        "    internal static partial class NativeCalls",
        "    {",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotObjectReleaseRefCounted(IntPtr nativePtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern string GodotVariantStringify(Variant variant);",
        "",        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotCallableCreate(IntPtr targetPtr, string method);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotCallableCreateDelegate(long delegateId);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern bool GodotCallableIsValid(IntPtr callablePtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern string GodotCallableGetMethod(IntPtr callablePtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern Variant GodotCallableCall(IntPtr callablePtr, Variant[] varargs);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotCallableBind(IntPtr callablePtr, Variant[] varargs);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotSignalCreate(IntPtr targetPtr, string signal);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern bool GodotSignalIsNull(IntPtr signalPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern string GodotSignalGetName(IntPtr signalPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotSignalConnect(IntPtr signalPtr, IntPtr callablePtr, int flags);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotSignalEmit(IntPtr signalPtr, Variant[] varargs);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotPackedStringArrayCreate();",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedStringArrayDestroy(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotPackedStringArraySize(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern string GodotPackedStringArrayGet(IntPtr arrayPtr, int index);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedStringArrayAppend(IntPtr arrayPtr, string value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotPackedByteArrayCreate();",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotPackedByteArraySize(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern byte GodotPackedByteArrayGet(IntPtr arrayPtr, int index);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedByteArraySet(IntPtr arrayPtr, int index, byte value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedByteArrayAdd(IntPtr arrayPtr, byte value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedByteArrayClear(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotPackedInt32ArrayCreate();",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotPackedInt32ArraySize(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotPackedInt32ArrayGet(IntPtr arrayPtr, int index);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedInt32ArraySet(IntPtr arrayPtr, int index, int value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedInt32ArrayAdd(IntPtr arrayPtr, int value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedInt32ArrayClear(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotPackedInt64ArrayCreate();",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotPackedInt64ArraySize(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern long GodotPackedInt64ArrayGet(IntPtr arrayPtr, int index);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedInt64ArraySet(IntPtr arrayPtr, int index, long value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedInt64ArrayAdd(IntPtr arrayPtr, long value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedInt64ArrayClear(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotPackedFloat32ArrayCreate();",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotPackedFloat32ArraySize(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern float GodotPackedFloat32ArrayGet(IntPtr arrayPtr, int index);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedFloat32ArraySet(IntPtr arrayPtr, int index, float value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedFloat32ArrayAdd(IntPtr arrayPtr, float value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedFloat32ArrayClear(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotPackedFloat64ArrayCreate();",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotPackedFloat64ArraySize(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern double GodotPackedFloat64ArrayGet(IntPtr arrayPtr, int index);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedFloat64ArraySet(IntPtr arrayPtr, int index, double value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedFloat64ArrayAdd(IntPtr arrayPtr, double value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedFloat64ArrayClear(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotPackedVector2ArrayCreate();",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotPackedVector2ArraySize(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern Vector2 GodotPackedVector2ArrayGet(IntPtr arrayPtr, int index);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedVector2ArraySet(IntPtr arrayPtr, int index, Vector2 value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedVector2ArrayAdd(IntPtr arrayPtr, Vector2 value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedVector2ArrayClear(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotPackedVector3ArrayCreate();",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotPackedVector3ArraySize(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern Vector3 GodotPackedVector3ArrayGet(IntPtr arrayPtr, int index);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedVector3ArraySet(IntPtr arrayPtr, int index, Vector3 value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedVector3ArrayAdd(IntPtr arrayPtr, Vector3 value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedVector3ArrayClear(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotPackedColorArrayCreate();",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotPackedColorArraySize(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern Color GodotPackedColorArrayGet(IntPtr arrayPtr, int index);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedColorArraySet(IntPtr arrayPtr, int index, Color value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedColorArrayAdd(IntPtr arrayPtr, Color value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotPackedColorArrayClear(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotOpaqueValueDestroy(IntPtr valuePtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotArrayCreate();",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotArraySize(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern Variant GodotArrayGet(IntPtr arrayPtr, int index);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotArraySet(IntPtr arrayPtr, int index, Variant value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotArrayAdd(IntPtr arrayPtr, Variant value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotArrayInsert(IntPtr arrayPtr, int index, Variant value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotArrayRemoveAt(IntPtr arrayPtr, int index);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotArrayClear(IntPtr arrayPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern bool GodotArrayContains(IntPtr arrayPtr, Variant value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotArrayIndexOf(IntPtr arrayPtr, Variant value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotDictionaryCreate();",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern int GodotDictionarySize(IntPtr dictionaryPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern bool GodotDictionaryContainsKey(IntPtr dictionaryPtr, Variant key);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern Variant GodotDictionaryGet(IntPtr dictionaryPtr, Variant key);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotDictionarySet(IntPtr dictionaryPtr, Variant key, Variant value);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern bool GodotDictionaryRemove(IntPtr dictionaryPtr, Variant key);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern void GodotDictionaryClear(IntPtr dictionaryPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotDictionaryKeys(IntPtr dictionaryPtr);",
        "",
        "        [MethodImpl(MethodImplOptions.InternalCall)]",
        "        internal static extern IntPtr GodotDictionaryValues(IntPtr dictionaryPtr);",
        "",
    ]
    for method in methods:
        if method.return_type.category in {"packed_string_array", "packed_array", "opaque_variant", "typed_array", "opaque_value", "object", "refcounted"}:
            return_type = "IntPtr"
        elif method.return_type.category == "variant":
            return_type = "Variant"
        elif method.return_type.category == "string":
            return_type = "string"
        elif method.return_type.category == "enum":
            return_type = "int"
        elif method.return_type.category == "bitfield":
            return_type = "long"
        elif method.return_type.category in {"vector2", "vector2i", "vector3", "vector3i", "color", "rect2", "rect2i", "transform2d", "aabb", "quaternion", "basis", "transform3d", "vector4", "vector4i", "plane", "projection", "rid"}:
            return_type = method.return_type.managed_type
        else:
            return_type = method.return_type.managed_type if method.return_type.category != "void" else "void"
        args = [] if method.is_static else ["IntPtr nativePtr"]
        for arg in method.args:
            if arg["type"].category == "variant":
                args.append(f"Variant {camel_name(arg['name'])}")
            elif arg["type"].category in {"packed_string_array", "packed_array", "opaque_variant", "typed_array", "opaque_value"}:
                args.append(f"IntPtr {camel_name(arg['name'])}Ptr")
            elif arg["type"].category == "native_pointer":
                args.append(f"IntPtr {camel_name(arg['name'])}")
            elif arg["type"].category in {"object", "refcounted"}:
                args.append(f"IntPtr {camel_name(arg['name'])}Ptr")
            elif arg["type"].category == "string":
                args.append(f"string {camel_name(arg['name'])}")
            elif arg["type"].category == "enum":
                args.append(f"int {camel_name(arg['name'])}")
            elif arg["type"].category == "bitfield":
                args.append(f"long {camel_name(arg['name'])}")
            elif arg["type"].category in {"vector2", "vector2i", "vector3", "vector3i", "color", "rect2", "rect2i", "transform2d", "aabb", "quaternion", "basis", "transform3d", "vector4", "vector4i", "plane", "projection", "rid"}:
                args.append(f"{arg['type'].managed_type} {camel_name(arg['name'])}")
            else:
                args.append(managed_arg_declaration(arg))
        if method.is_vararg:
            args.append("Variant[] varargs")
        native_call_lines.extend(
            [
                "        [MethodImpl(MethodImplOptions.InternalCall)]",
                f"        internal static extern {return_type} Godot{method.cs_class_name}{method.icall_suffix}({', '.join(args)});",
                "",
            ]
        )
    native_call_lines.extend(["    }", "}", ""])
    write(generated / "NativeCalls.generated.cs", "\n".join(native_call_lines))


def cpp_cast_type(type_info):
    return type_info.cpp_type


def cpp_return_statement(method, call):
    category = method.return_type.category
    if category == "void":
        return f"    {call};\n    return leanclr::core::Unit{{}};"
    if category == "string":
        return f"    return to_rt_string({call});"
    if category == "variant":
        return f"    return to_managed_variant({call});"
    if category == "packed_string_array":
        return f"    return new_packed_string_array({call});"
    if category in {"packed_array", "opaque_variant", "typed_array", "opaque_value"}:
        return f"    return new_opaque_value({call});"
    if category == "object":
        return f"    return reinterpret_cast<intptr_t>({call});"
    if category == "native_pointer":
        return f"    return reinterpret_cast<intptr_t>({call});"
    if category == "refcounted":
        return f"    return retain_refcounted({call});"
    if category == "enum":
        return f"    return static_cast<int32_t>({call});"
    if category == "bitfield":
        return f"    return static_cast<int64_t>({call});"
    if category == "float":
        return f"    return static_cast<float>({call});"
    return f"    return {call};"


def cpp_native_param_declaration(arg):
    name = camel_name(arg["name"])
    typ = arg["type"]
    if typ.category == "string":
        return f"leanclr::vm::RtString* p_{name}"
    if typ.category == "variant":
        return f"ManagedVariant p_{name}"
    if typ.category in {"packed_string_array", "packed_array", "opaque_variant", "typed_array", "opaque_value"}:
        return f"intptr_t p_{name}_ptr"
    if typ.category == "native_pointer":
        return f"intptr_t p_{name}"
    if typ.category in {"object", "refcounted"}:
        return f"intptr_t p_{name}_ptr"
    if typ.category == "enum":
        return f"int32_t p_{name}"
    if typ.category == "bitfield":
        return f"int64_t p_{name}"
    return f"{typ.native_type} p_{name}"


def cpp_call_arg(arg):
    name = camel_name(arg["name"])
    typ = arg["type"]
    if typ.category == "string":
        if typ.cpp_type == "StringName":
            return f"StringName(rt_string_to_godot(p_{name}))"
        if typ.cpp_type == "NodePath":
            return f"NodePath(rt_string_to_godot(p_{name}))"
        return f"rt_string_to_godot(p_{name})"
    if typ.category == "variant":
        return f"variant_arg(p_{name})"
    if typ.category == "packed_string_array":
        return f"packed_string_array_arg(p_{name}_ptr)"
    if typ.category in {"packed_array", "opaque_variant", "typed_array", "opaque_value"}:
        return f"opaque_value_arg<{typ.cpp_type}>(p_{name}_ptr)"
    if typ.category == "native_pointer":
        return f"reinterpret_cast<{typ.cpp_type}>(p_{name})"
    if typ.category == "object":
        return f"as_godot_object<{cpp_cast_type(typ)}>(p_{name}_ptr)"
    if typ.category == "refcounted":
        return f"Ref<{cpp_cast_type(typ)}>(as_godot_object<{cpp_cast_type(typ)}>(p_{name}_ptr))"
    if typ.category == "enum":
        return f"static_cast<{typ.cpp_type}>(p_{name})"
    if typ.category == "bitfield":
        return f"{typ.cpp_type}(p_{name})"
    if typ.category == "int" and typ.cpp_type and typ.cpp_type != typ.native_type:
        return f"static_cast<{typ.cpp_type}>(p_{name})"
    return f"p_{name}"


def cpp_self_type(method):
    return "Object" if method.class_name == "Object" else method.cpp_class_name


def append_formal_vararg(array_name, arg):
    category = arg["type"].category
    expression = cpp_call_arg(arg)
    if category == "void":
        return ""
    if category == "enum":
        expression = f"static_cast<int32_t>({expression})"
    if category == "bitfield":
        expression = f"static_cast<int64_t>({expression})"
    return f"    {array_name}.append(Variant({expression}));"


def vararg_return_statement(method, result_name):
    category = method.return_type.category
    if category == "void":
        return "    return leanclr::core::Unit{};"
    if category == "variant":
        return f"    return to_managed_variant({result_name});"
    if category == "enum":
        return f"    return static_cast<int32_t>(static_cast<int64_t>({result_name}));"
    if category == "bitfield":
        return f"    return static_cast<int64_t>({result_name});"
    if category == "bool":
        return f"    return static_cast<bool>({result_name});"
    if category == "int":
        return f"    return static_cast<int64_t>({result_name});"
    if category == "float":
        return f"    return static_cast<float>(static_cast<double>({result_name}));"
    if category == "string":
        return f"    return to_rt_string(static_cast<String>({result_name}));"
    if category in {"object", "refcounted"}:
        return f"    return reinterpret_cast<intptr_t>(static_cast<Object*>({result_name}));"
    return f"    return {method.return_type.native_type}();"


def generate_native_vararg_method_function(method):
    fn = native_function_name(method)
    params = ([] if method.is_static else ["intptr_t p_native_ptr"]) + [cpp_native_param_declaration(arg) for arg in method.args] + ["leanclr::vm::RtArray* p_varargs"]
    self_type = "Object"
    setup_lines = []
    if not method.is_static:
        setup_lines.extend(
            [
                f"    {self_type}* self = as_godot_object<{self_type}>(p_native_ptr);",
                "    if (self == nullptr)",
                "    {",
                f"        { {'void': 'return leanclr::core::Unit{};', 'variant': 'return to_managed_variant(Variant());', 'enum': 'return 0;'}.get(method.return_type.category, 'return ' + method.return_type.native_type + '();') }",
                "    }",
                "",
            ]
        )
    setup_lines.append("    Array args;")
    if method.class_name == "Object" and method.api_name == "call":
        call_method = "rt_string_to_godot(p_method)"
    else:
        call_method = f"StringName(\"{method.api_name}\")"
        for arg in method.args:
            setup_lines.append(append_formal_vararg("args", arg))
    setup_lines.append("    append_managed_varargs(args, p_varargs);")
    target = method.cpp_class_name if method.is_static else "self"
    if method.return_type.category == "void":
        call_lines = [f"    {target}->callv({call_method}, args);", *vararg_return_statement(method, "result").splitlines()]
    else:
        call_lines = [f"    Variant result = {target}->callv({call_method}, args);", *vararg_return_statement(method, "result").splitlines()]
    return f"""{method.return_type.native_type} {fn}({', '.join(params)}) noexcept
{{
{chr(10).join(line for line in setup_lines if line is not None)}
{chr(10).join(call_lines)}
}}
"""


def generate_native_method_function(method):
    fn = native_function_name(method)
    if method.is_vararg:
        return generate_native_vararg_method_function(method)
    params = ([] if method.is_static else ["intptr_t p_native_ptr"]) + [cpp_native_param_declaration(arg) for arg in method.args]
    call_args = ", ".join(cpp_call_arg(arg) for arg in method.args)
    if method.is_static:
        call = f"{method.cpp_class_name}::{method.cpp_name}({call_args})" if call_args else f"{method.cpp_class_name}::{method.cpp_name}()"
        return f"""{method.return_type.native_type} {fn}({', '.join(params)}) noexcept
{{
{cpp_return_statement(method, call)}
}}
"""

    self_type = cpp_self_type(method)
    call = f"self->{method.cpp_name}({call_args})" if call_args else f"self->{method.cpp_name}()"
    null_return = {
        "void": "return leanclr::core::Unit{};",
        "string": "return leanclr::vm::String::get_empty_string();",
        "variant": "return to_managed_variant(Variant());",
        "packed_string_array": "return new_packed_string_array(PackedStringArray());",
        "packed_array": f"return 0;",
        "opaque_variant": f"return 0;",
        "typed_array": f"return 0;",
        "opaque_value": f"return 0;",
        "object": "return 0;",
        "native_pointer": "return 0;",
        "refcounted": "return 0;",
        "bool": "return false;",
        "int": "return 0;",
        "float": "return 0.0f;",
        "enum": "return 0;",
        "bitfield": "return 0;",
        "vector2": "return Vector2();",
        "vector2i": "return Vector2i();",
        "vector3": "return Vector3();",
        "vector3i": "return Vector3i();",
        "color": "return Color();",
        "rect2": "return Rect2();",
        "rect2i": "return Rect2i();",
        "transform2d": "return Transform2D();",
        "aabb": "return AABB();",
        "quaternion": "return Quaternion();",
        "basis": "return Basis();",
        "transform3d": "return Transform3D();",
        "vector4": "return Vector4();",
        "vector4i": "return Vector4i();",
        "plane": "return Plane();",
        "projection": "return Projection();",
        "rid": "return RID();",
    }[method.return_type.category]
    return f"""{method.return_type.native_type} {fn}({', '.join(params)}) noexcept
{{
    {self_type}* self = as_godot_object<{self_type}>(p_native_ptr);
    if (self == nullptr)
    {{
        {null_return}
    }}

{cpp_return_statement(method, call)}
}}
"""


def cpp_invoker_param_get(arg, index):
    name = camel_name(arg["name"])
    typ = arg["type"]
    if typ.category == "variant":
        return f"    ManagedVariant arg_{name} = leanclr::interp::EvalStackOp::get_param<ManagedVariant>(p_params, {index});"
    if typ.category in {"packed_string_array", "packed_array", "opaque_variant", "typed_array", "opaque_value", "object", "refcounted"}:
        return f"    const intptr_t arg_{name}_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, {index});"
    return f"    {typ.stack_type} arg_{name} = leanclr::interp::EvalStackOp::get_param<{typ.stack_type}>(p_params, {index});"


def generate_native_invoker(method):
    fn = native_function_name(method)
    invoker = f"{fn}_invoker"
    param_reads = [] if method.is_static else ["    const intptr_t p_native_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);"]
    call_args = [] if method.is_static else ["p_native_ptr"]
    arg_offset = 0 if method.is_static else 1
    for arg in method.args:
        param_reads.append(cpp_invoker_param_get(arg, arg_offset))
        arg_offset += arg["type"].stack_slots
        name = camel_name(arg["name"])
        call_args.append(f"arg_{name}_ptr" if arg["type"].category in {"packed_string_array", "packed_array", "opaque_variant", "typed_array", "opaque_value", "object", "refcounted"} else f"arg_{name}")
    if method.is_vararg:
        param_reads.append(f"    leanclr::vm::RtArray* p_varargs = leanclr::interp::EvalStackOp::get_param<leanclr::vm::RtArray*>(p_params, {arg_offset});")
        call_args.append("p_varargs")
    if method.return_type.category == "void":
        body = f"    return {fn}({', '.join(call_args)});"
    else:
        body = f"    leanclr::interp::EvalStackOp::set_return(p_ret, {fn}({', '.join(call_args)}));\n    return leanclr::core::Unit{{}};"
    return f"""leanclr::RtResultVoid {invoker}(leanclr::metadata::RtManagedMethodPointer p_method_ptr,
                                       const leanclr::metadata::RtMethodInfo* p_method,
                                       const leanclr::interp::RtStackObject* p_params,
                                       leanclr::interp::RtStackObject* p_ret) noexcept
{{
    (void)p_method_ptr;
    (void)p_method;
    (void)p_params;
    (void)p_ret;
{chr(10).join(param_reads)}
{body}
}}
"""


def generate_native(classes, methods, src_dir):
    methods = [method for method in methods if not method.is_virtual]
    write(
        src_dir / "generated" / "godot_api.generated.h",
        """#pragma once

namespace godot
{

void register_generated_godot_api_icalls();

} // namespace godot
""",
    )

    includes = ["#include \"godot_api.generated.h\"", ""]
    bound_classes = {method.class_name for method in methods}
    for method in methods:
        if method.return_type.category in {"object", "refcounted"}:
            bound_classes.add(method.return_type.cpp_type)
        for arg in method.args:
            if arg["type"].category in {"object", "refcounted"}:
                bound_classes.add(arg["type"].cpp_type)
    bound_classes = sorted(bound_classes)
    for class_name in bound_classes:
        includes.append(f"#include <godot_cpp/classes/{cpp_header_name(class_name)}.hpp>")
    includes.extend(
        [
            "#include <godot_cpp/variant/char_string.hpp>",
            "#include <godot_cpp/variant/node_path.hpp>",
            "#include <godot_cpp/variant/aabb.hpp>",
            "#include <godot_cpp/variant/array.hpp>",
            "#include <godot_cpp/variant/basis.hpp>",
            "#include <godot_cpp/variant/callable.hpp>",
            "#include <godot_cpp/variant/color.hpp>",
            "#include <godot_cpp/variant/dictionary.hpp>",
            "#include <godot_cpp/variant/packed_byte_array.hpp>",
            "#include <godot_cpp/variant/packed_color_array.hpp>",
            "#include <godot_cpp/variant/packed_float32_array.hpp>",
            "#include <godot_cpp/variant/packed_float64_array.hpp>",
            "#include <godot_cpp/variant/packed_int32_array.hpp>",
            "#include <godot_cpp/variant/packed_int64_array.hpp>",
            "#include <godot_cpp/variant/packed_string_array.hpp>",
            "#include <godot_cpp/variant/packed_vector2_array.hpp>",
            "#include <godot_cpp/variant/packed_vector3_array.hpp>",
            "#include <godot_cpp/variant/plane.hpp>",
            "#include <godot_cpp/variant/rect2.hpp>",
            "#include <godot_cpp/variant/rect2i.hpp>",
            "#include <godot_cpp/variant/rid.hpp>",
            "#include <godot_cpp/variant/signal.hpp>",
            "#include <godot_cpp/variant/projection.hpp>",
            "#include <godot_cpp/variant/quaternion.hpp>",
            "#include <godot_cpp/variant/string.hpp>",
            "#include <godot_cpp/variant/string_name.hpp>",
            "#include <godot_cpp/variant/transform2d.hpp>",
            "#include <godot_cpp/variant/transform3d.hpp>",
            "#include <godot_cpp/variant/typed_array.hpp>",
            "#include <godot_cpp/variant/vector2.hpp>",
            "#include <godot_cpp/variant/vector2i.hpp>",
            "#include <godot_cpp/variant/vector3.hpp>",
            "#include <godot_cpp/variant/vector3i.hpp>",
            "#include <godot_cpp/variant/vector4.hpp>",
            "#include <godot_cpp/variant/vector4i.hpp>",
            "#include <godot_cpp/variant/variant.hpp>",
            "",
            "#include \"interp/eval_stack_op.h\"",
            "#include \"vm/internal_calls.h\"",
            "#include \"vm/rt_array.h\"",
            "#include \"vm/rt_string.h\"",
            "",
        ]
    )

    body = [
        "// <auto-generated />",
        *includes,
        "namespace godot",
        "{",
        "namespace",
        "{",
        "",
        "enum ManagedVariantType : int32_t",
        "{",
        "    MANAGED_VARIANT_TYPE_NIL = 0,",
        "    MANAGED_VARIANT_TYPE_BOOL = 1,",
        "    MANAGED_VARIANT_TYPE_INT = 2,",
        "    MANAGED_VARIANT_TYPE_FLOAT = 3,",
        "    MANAGED_VARIANT_TYPE_STRING = 4,",
        "    MANAGED_VARIANT_TYPE_VECTOR2 = 5,",
        "    MANAGED_VARIANT_TYPE_VECTOR2I = 6,",
        "    MANAGED_VARIANT_TYPE_RECT2 = 7,",
        "    MANAGED_VARIANT_TYPE_RECT2I = 8,",
        "    MANAGED_VARIANT_TYPE_VECTOR3 = 9,",
        "    MANAGED_VARIANT_TYPE_VECTOR3I = 10,",
        "    MANAGED_VARIANT_TYPE_TRANSFORM2D = 11,",
        "    MANAGED_VARIANT_TYPE_VECTOR4 = 12,",
        "    MANAGED_VARIANT_TYPE_VECTOR4I = 13,",
        "    MANAGED_VARIANT_TYPE_PLANE = 14,",
        "    MANAGED_VARIANT_TYPE_QUATERNION = 15,",
        "    MANAGED_VARIANT_TYPE_AABB = 16,",
        "    MANAGED_VARIANT_TYPE_BASIS = 17,",
        "    MANAGED_VARIANT_TYPE_TRANSFORM3D = 18,",
        "    MANAGED_VARIANT_TYPE_PROJECTION = 19,",
        "    MANAGED_VARIANT_TYPE_COLOR = 20,",
        "    MANAGED_VARIANT_TYPE_STRING_NAME = 21,",
        "    MANAGED_VARIANT_TYPE_NODE_PATH = 22,",
        "    MANAGED_VARIANT_TYPE_RID = 23,",
        "    MANAGED_VARIANT_TYPE_OBJECT = 24,"
        "    MANAGED_VARIANT_TYPE_CALLABLE = 25,"
        "    MANAGED_VARIANT_TYPE_SIGNAL = 26,"
        "    MANAGED_VARIANT_TYPE_DICTIONARY = 27,",
        "    MANAGED_VARIANT_TYPE_ARRAY = 28,",
        "    MANAGED_VARIANT_TYPE_PACKED_BYTE_ARRAY = 29,",
        "    MANAGED_VARIANT_TYPE_PACKED_INT32_ARRAY = 30,",
        "    MANAGED_VARIANT_TYPE_PACKED_INT64_ARRAY = 31,",
        "    MANAGED_VARIANT_TYPE_PACKED_FLOAT32_ARRAY = 32,",
        "    MANAGED_VARIANT_TYPE_PACKED_FLOAT64_ARRAY = 33,",
        "    MANAGED_VARIANT_TYPE_PACKED_STRING_ARRAY = 34,",
        "    MANAGED_VARIANT_TYPE_PACKED_VECTOR2_ARRAY = 35,",
        "    MANAGED_VARIANT_TYPE_PACKED_VECTOR3_ARRAY = 36,",
        "    MANAGED_VARIANT_TYPE_PACKED_COLOR_ARRAY = 37,",
        "};",
        "",
        "struct ManagedVector2 { float x; float y; };",
        "struct ManagedVector2i { int32_t x; int32_t y; };",
        "struct ManagedVector3 { float x; float y; float z; };",
        "struct ManagedVector3i { int32_t x; int32_t y; int32_t z; };",
        "struct ManagedVector4 { float x; float y; float z; float w; };",
        "struct ManagedVector4i { int32_t x; int32_t y; int32_t z; int32_t w; };",
        "struct ManagedColor { float r; float g; float b; float a; };",
        "struct ManagedRect2 { ManagedVector2 position; ManagedVector2 size; };",
        "struct ManagedRect2i { ManagedVector2i position; ManagedVector2i size; };",
        "struct ManagedTransform2D { ManagedVector2 x; ManagedVector2 y; ManagedVector2 origin; };",
        "struct ManagedAABB { ManagedVector3 position; ManagedVector3 size; };",
        "struct ManagedQuaternion { float x; float y; float z; float w; };",
        "struct ManagedBasis { ManagedVector3 x; ManagedVector3 y; ManagedVector3 z; };",
        "struct ManagedTransform3D { ManagedBasis basis; ManagedVector3 origin; };",
        "struct ManagedPlane { ManagedVector3 normal; float d; };",
        "struct ManagedProjection { ManagedVector4 x; ManagedVector4 y; ManagedVector4 z; ManagedVector4 w; };",
        "",
        "struct ManagedVariant",
        "{",
        "    int32_t type = MANAGED_VARIANT_TYPE_NIL;",
        "    int32_t flags = 0;",
        "    union",
        "    {",
        "        bool bool_value;",
        "        int64_t int_value;",
        "        double float_value;",
        "        leanclr::vm::RtString* string_value;",
        "        int64_t rid_value;",
        "        intptr_t native_ptr;",
        "        ManagedVector2 vector2_value;",
        "        ManagedVector2i vector2i_value;",
        "        ManagedVector3 vector3_value;",
        "        ManagedVector3i vector3i_value;",
        "        ManagedVector4 vector4_value;",
        "        ManagedVector4i vector4i_value;",
        "        ManagedColor color_value;",
        "        ManagedRect2 rect2_value;",
        "        ManagedRect2i rect2i_value;",
        "        ManagedTransform2D transform2d_value;",
        "        ManagedAABB aabb_value;",
        "        ManagedQuaternion quaternion_value;",
        "        ManagedBasis basis_value;",
        "        ManagedTransform3D transform3d_value;",
        "        ManagedPlane plane_value;",
        "        ManagedProjection projection_value;",
        "    };",
        "};",
        "",
        "String rt_string_to_godot(const leanclr::vm::RtString* p_string)",
        "{",
        "    if (p_string == nullptr)",
        "    {",
        "        return String();",
        "    }",
        "",
        "    String result;",
        "    for (int32_t i = 0; i < p_string->length; ++i)",
        "    {",
        "        result += String::chr(static_cast<char32_t>(*(&p_string->first_char + i)));",
        "    }",
        "    return result;",
        "}",
        "",
        "leanclr::vm::RtString* to_rt_string(const String& p_string)",
        "{",
        "    const CharString utf8 = p_string.utf8();",
        "    return leanclr::vm::String::create_string_from_utf8cstr(utf8.get_data());",
        "}",
        "",
        "leanclr::vm::RtString* to_rt_string(const StringName& p_string_name)",
        "{",
        "    return to_rt_string(String(p_string_name));",
        "}",
        "",
        "struct OpaqueValue",
        "{",
        "    void* value = nullptr;",
        "    void (*destroy)(void*) = nullptr;",
        "};",
        "",
        "template <typename T>",
        "void destroy_opaque_value(void* p_value)",
        "{",
        "    memdelete(reinterpret_cast<T*>(p_value));",
        "}",
        "",
        "template <typename T>",
        "intptr_t new_opaque_value(const T& p_value)",
        "{",
        "    OpaqueValue* opaque = memnew(OpaqueValue);",
        "    opaque->value = memnew(T(p_value));",
        "    opaque->destroy = &destroy_opaque_value<T>;",
        "    return reinterpret_cast<intptr_t>(opaque);",
        "}",
        "",
        "template <typename T>",
        "T* opaque_value_ptr(intptr_t p_value_ptr)",
        "{",
        "    OpaqueValue* opaque = reinterpret_cast<OpaqueValue*>(p_value_ptr);",
        "    return opaque != nullptr && opaque->value != nullptr ? reinterpret_cast<T*>(opaque->value) : nullptr;",
        "}",
        "",
        "template <typename T>",
        "T opaque_value_arg(intptr_t p_value_ptr)",
        "{",
        "    T* value = opaque_value_ptr<T>(p_value_ptr);",
        "    return value != nullptr ? *value : T();",
        "}",
        "",
        "intptr_t new_packed_string_array(const PackedStringArray& p_array);",
        "PackedStringArray packed_string_array_arg(intptr_t p_array_ptr);",
        "",
        "ManagedVariant to_managed_variant(const Variant& p_variant)",
        "{",
        "    ManagedVariant result;",
        "    switch (p_variant.get_type())",
        "    {",
        "        case Variant::BOOL:",
        "            result.type = MANAGED_VARIANT_TYPE_BOOL;",
        "            result.bool_value = static_cast<bool>(p_variant);",
        "            break;",
        "        case Variant::INT:",
        "            result.type = MANAGED_VARIANT_TYPE_INT;",
        "            result.int_value = static_cast<int64_t>(p_variant);",
        "            break;",
        "        case Variant::FLOAT:",
        "            result.type = MANAGED_VARIANT_TYPE_FLOAT;",
        "            result.float_value = static_cast<double>(p_variant);",
        "            break;",
        "        case Variant::STRING:",
        "            result.type = MANAGED_VARIANT_TYPE_STRING;",
        "            result.string_value = to_rt_string(static_cast<String>(p_variant));",
        "            break;",
        "        case Variant::STRING_NAME:",
        "            result.type = MANAGED_VARIANT_TYPE_STRING_NAME;",
        "            result.string_value = to_rt_string(static_cast<StringName>(p_variant));",
        "            break;",
        "        case Variant::NODE_PATH:",
        "            result.type = MANAGED_VARIANT_TYPE_NODE_PATH;",
        "            result.string_value = to_rt_string(String(static_cast<NodePath>(p_variant)));",
        "            break;",
        "        case Variant::RID:",
        "            result.type = MANAGED_VARIANT_TYPE_RID;",
        "            { const RID value = static_cast<RID>(p_variant); result.rid_value = value.get_id(); }",
        "            break;",
        "        case Variant::VECTOR2:",
        "            result.type = MANAGED_VARIANT_TYPE_VECTOR2;",
        "            { const Vector2 value = static_cast<Vector2>(p_variant); result.vector2_value = ManagedVector2{value.x, value.y}; }",
        "            break;",
        "        case Variant::VECTOR2I:",
        "            result.type = MANAGED_VARIANT_TYPE_VECTOR2I;",
        "            { const Vector2i value = static_cast<Vector2i>(p_variant); result.vector2i_value = ManagedVector2i{value.x, value.y}; }",
        "            break;",
        "        case Variant::RECT2:",
        "            result.type = MANAGED_VARIANT_TYPE_RECT2;",
        "            { const Rect2 value = static_cast<Rect2>(p_variant); result.rect2_value = ManagedRect2{ManagedVector2{value.position.x, value.position.y}, ManagedVector2{value.size.x, value.size.y}}; }",
        "            break;",
        "        case Variant::RECT2I:",
        "            result.type = MANAGED_VARIANT_TYPE_RECT2I;",
        "            { const Rect2i value = static_cast<Rect2i>(p_variant); result.rect2i_value = ManagedRect2i{ManagedVector2i{value.position.x, value.position.y}, ManagedVector2i{value.size.x, value.size.y}}; }",
        "            break;",
        "        case Variant::VECTOR3:",
        "            result.type = MANAGED_VARIANT_TYPE_VECTOR3;",
        "            { const Vector3 value = static_cast<Vector3>(p_variant); result.vector3_value = ManagedVector3{value.x, value.y, value.z}; }",
        "            break;",
        "        case Variant::VECTOR3I:",
        "            result.type = MANAGED_VARIANT_TYPE_VECTOR3I;",
        "            { const Vector3i value = static_cast<Vector3i>(p_variant); result.vector3i_value = ManagedVector3i{value.x, value.y, value.z}; }",
        "            break;",
        "        case Variant::TRANSFORM2D:",
        "            result.type = MANAGED_VARIANT_TYPE_TRANSFORM2D;",
        "            { const Transform2D value = static_cast<Transform2D>(p_variant); result.transform2d_value = ManagedTransform2D{ManagedVector2{value.columns[0].x, value.columns[0].y}, ManagedVector2{value.columns[1].x, value.columns[1].y}, ManagedVector2{value.columns[2].x, value.columns[2].y}}; }",
        "            break;",
        "        case Variant::VECTOR4:",
        "            result.type = MANAGED_VARIANT_TYPE_VECTOR4;",
        "            { const Vector4 value = static_cast<Vector4>(p_variant); result.vector4_value = ManagedVector4{value.x, value.y, value.z, value.w}; }",
        "            break;",
        "        case Variant::VECTOR4I:",
        "            result.type = MANAGED_VARIANT_TYPE_VECTOR4I;",
        "            { const Vector4i value = static_cast<Vector4i>(p_variant); result.vector4i_value = ManagedVector4i{value.x, value.y, value.z, value.w}; }",
        "            break;",
        "        case Variant::PLANE:",
        "            result.type = MANAGED_VARIANT_TYPE_PLANE;",
        "            { const Plane value = static_cast<Plane>(p_variant); result.plane_value = ManagedPlane{ManagedVector3{value.normal.x, value.normal.y, value.normal.z}, value.d}; }",
        "            break;",
        "        case Variant::QUATERNION:",
        "            result.type = MANAGED_VARIANT_TYPE_QUATERNION;",
        "            { const Quaternion value = static_cast<Quaternion>(p_variant); result.quaternion_value = ManagedQuaternion{value.x, value.y, value.z, value.w}; }",
        "            break;",
        "        case Variant::AABB:",
        "            result.type = MANAGED_VARIANT_TYPE_AABB;",
        "            { const AABB value = static_cast<AABB>(p_variant); result.aabb_value = ManagedAABB{ManagedVector3{value.position.x, value.position.y, value.position.z}, ManagedVector3{value.size.x, value.size.y, value.size.z}}; }",
        "            break;",
        "        case Variant::BASIS:",
        "            result.type = MANAGED_VARIANT_TYPE_BASIS;",
        "            { const Basis value = static_cast<Basis>(p_variant); result.basis_value = ManagedBasis{ManagedVector3{value.rows[0].x, value.rows[0].y, value.rows[0].z}, ManagedVector3{value.rows[1].x, value.rows[1].y, value.rows[1].z}, ManagedVector3{value.rows[2].x, value.rows[2].y, value.rows[2].z}}; }",
        "            break;",
        "        case Variant::TRANSFORM3D:",
        "            result.type = MANAGED_VARIANT_TYPE_TRANSFORM3D;",
        "            { const Transform3D value = static_cast<Transform3D>(p_variant); result.transform3d_value = ManagedTransform3D{ManagedBasis{ManagedVector3{value.basis.rows[0].x, value.basis.rows[0].y, value.basis.rows[0].z}, ManagedVector3{value.basis.rows[1].x, value.basis.rows[1].y, value.basis.rows[1].z}, ManagedVector3{value.basis.rows[2].x, value.basis.rows[2].y, value.basis.rows[2].z}}, ManagedVector3{value.origin.x, value.origin.y, value.origin.z}}; }",
        "            break;",
        "        case Variant::PROJECTION:",
        "            result.type = MANAGED_VARIANT_TYPE_PROJECTION;",
        "            { const Projection value = static_cast<Projection>(p_variant); result.projection_value = ManagedProjection{ManagedVector4{value.columns[0].x, value.columns[0].y, value.columns[0].z, value.columns[0].w}, ManagedVector4{value.columns[1].x, value.columns[1].y, value.columns[1].z, value.columns[1].w}, ManagedVector4{value.columns[2].x, value.columns[2].y, value.columns[2].z, value.columns[2].w}, ManagedVector4{value.columns[3].x, value.columns[3].y, value.columns[3].z, value.columns[3].w}}; }",
        "            break;",
        "        case Variant::COLOR:",
        "            result.type = MANAGED_VARIANT_TYPE_COLOR;",
        "            { const Color value = static_cast<Color>(p_variant); result.color_value = ManagedColor{value.r, value.g, value.b, value.a}; }",
        "            break;",
        "        case Variant::OBJECT:",
        "            result.type = MANAGED_VARIANT_TYPE_OBJECT;",
        "            result.native_ptr = reinterpret_cast<intptr_t>(static_cast<Object*>(p_variant));",
        "            break;",
        "        case Variant::ARRAY:",
        "            result.type = MANAGED_VARIANT_TYPE_ARRAY;",
        "            result.flags = 1;",
        "            result.native_ptr = new_opaque_value(static_cast<Array>(p_variant));",
        "            break;",
        "        case Variant::DICTIONARY:",
        "            result.type = MANAGED_VARIANT_TYPE_DICTIONARY;",
        "            result.flags = 1;",
        "            result.native_ptr = new_opaque_value(static_cast<Dictionary>(p_variant));",
        "            break;",
        "        case Variant::CALLABLE:",
        "            result.type = MANAGED_VARIANT_TYPE_CALLABLE;",
        "            result.flags = 1;",
        "            result.native_ptr = new_opaque_value(static_cast<Callable>(p_variant));",
        "            break;",
        "        case Variant::SIGNAL:",
        "            result.type = MANAGED_VARIANT_TYPE_SIGNAL;",
        "            result.flags = 1;",
        "            result.native_ptr = new_opaque_value(static_cast<Signal>(p_variant));",
        "            break;",
        "        case Variant::PACKED_BYTE_ARRAY:",
        "            result.type = MANAGED_VARIANT_TYPE_PACKED_BYTE_ARRAY;",
        "            result.flags = 1;",
        "            result.native_ptr = new_opaque_value(static_cast<PackedByteArray>(p_variant));",
        "            break;",
        "        case Variant::PACKED_INT32_ARRAY:",
        "            result.type = MANAGED_VARIANT_TYPE_PACKED_INT32_ARRAY;",
        "            result.flags = 1;",
        "            result.native_ptr = new_opaque_value(static_cast<PackedInt32Array>(p_variant));",
        "            break;",
        "        case Variant::PACKED_INT64_ARRAY:",
        "            result.type = MANAGED_VARIANT_TYPE_PACKED_INT64_ARRAY;",
        "            result.flags = 1;",
        "            result.native_ptr = new_opaque_value(static_cast<PackedInt64Array>(p_variant));",
        "            break;",
        "        case Variant::PACKED_FLOAT32_ARRAY:",
        "            result.type = MANAGED_VARIANT_TYPE_PACKED_FLOAT32_ARRAY;",
        "            result.flags = 1;",
        "            result.native_ptr = new_opaque_value(static_cast<PackedFloat32Array>(p_variant));",
        "            break;",
        "        case Variant::PACKED_FLOAT64_ARRAY:",
        "            result.type = MANAGED_VARIANT_TYPE_PACKED_FLOAT64_ARRAY;",
        "            result.flags = 1;",
        "            result.native_ptr = new_opaque_value(static_cast<PackedFloat64Array>(p_variant));",
        "            break;",
        "        case Variant::PACKED_STRING_ARRAY:",
        "            result.type = MANAGED_VARIANT_TYPE_PACKED_STRING_ARRAY;",
        "            result.flags = 1;",
        "            result.native_ptr = new_packed_string_array(static_cast<PackedStringArray>(p_variant));",
        "            break;",
        "        case Variant::PACKED_VECTOR2_ARRAY:",
        "            result.type = MANAGED_VARIANT_TYPE_PACKED_VECTOR2_ARRAY;",
        "            result.flags = 1;",
        "            result.native_ptr = new_opaque_value(static_cast<PackedVector2Array>(p_variant));",
        "            break;",
        "        case Variant::PACKED_VECTOR3_ARRAY:",
        "            result.type = MANAGED_VARIANT_TYPE_PACKED_VECTOR3_ARRAY;",
        "            result.flags = 1;",
        "            result.native_ptr = new_opaque_value(static_cast<PackedVector3Array>(p_variant));",
        "            break;",
        "        case Variant::PACKED_COLOR_ARRAY:",
        "            result.type = MANAGED_VARIANT_TYPE_PACKED_COLOR_ARRAY;",
        "            result.flags = 1;",
        "            result.native_ptr = new_opaque_value(static_cast<PackedColorArray>(p_variant));",
        "            break;",
        "        default:",
        "            result.type = MANAGED_VARIANT_TYPE_NIL;",
        "            result.int_value = 0;",
        "            break;",
        "    }",
        "    return result;",
        "}",
        "",
        "Variant variant_arg(const ManagedVariant& p_variant)",
        "{",
        "    switch (p_variant.type)",
        "    {",
        "        case MANAGED_VARIANT_TYPE_BOOL:",
        "            return Variant(p_variant.bool_value);",
        "        case MANAGED_VARIANT_TYPE_INT:",
        "            return Variant(p_variant.int_value);",
        "        case MANAGED_VARIANT_TYPE_FLOAT:",
        "            return Variant(p_variant.float_value);",
        "        case MANAGED_VARIANT_TYPE_STRING:",
        "            return Variant(rt_string_to_godot(p_variant.string_value));",
        "        case MANAGED_VARIANT_TYPE_STRING_NAME:",
        "            return Variant(StringName(rt_string_to_godot(p_variant.string_value)));",
        "        case MANAGED_VARIANT_TYPE_NODE_PATH:",
        "            return Variant(NodePath(rt_string_to_godot(p_variant.string_value)));",
        "        case MANAGED_VARIANT_TYPE_RID:",
        "            { RID rid; *reinterpret_cast<int64_t*>(rid._native_ptr()) = p_variant.rid_value; return Variant(rid); }",
        "        case MANAGED_VARIANT_TYPE_VECTOR2:",
        "            return Variant(Vector2(p_variant.vector2_value.x, p_variant.vector2_value.y));",
        "        case MANAGED_VARIANT_TYPE_VECTOR2I:",
        "            return Variant(Vector2i(p_variant.vector2i_value.x, p_variant.vector2i_value.y));",
        "        case MANAGED_VARIANT_TYPE_RECT2:",
        "            return Variant(Rect2(Vector2(p_variant.rect2_value.position.x, p_variant.rect2_value.position.y), Vector2(p_variant.rect2_value.size.x, p_variant.rect2_value.size.y)));",
        "        case MANAGED_VARIANT_TYPE_RECT2I:",
        "            return Variant(Rect2i(Vector2i(p_variant.rect2i_value.position.x, p_variant.rect2i_value.position.y), Vector2i(p_variant.rect2i_value.size.x, p_variant.rect2i_value.size.y)));",
        "        case MANAGED_VARIANT_TYPE_VECTOR3:",
        "            return Variant(Vector3(p_variant.vector3_value.x, p_variant.vector3_value.y, p_variant.vector3_value.z));",
        "        case MANAGED_VARIANT_TYPE_VECTOR3I:",
        "            return Variant(Vector3i(p_variant.vector3i_value.x, p_variant.vector3i_value.y, p_variant.vector3i_value.z));",
        "        case MANAGED_VARIANT_TYPE_TRANSFORM2D:",
        "            return Variant(Transform2D(Vector2(p_variant.transform2d_value.x.x, p_variant.transform2d_value.x.y), Vector2(p_variant.transform2d_value.y.x, p_variant.transform2d_value.y.y), Vector2(p_variant.transform2d_value.origin.x, p_variant.transform2d_value.origin.y)));",
        "        case MANAGED_VARIANT_TYPE_VECTOR4:",
        "            return Variant(Vector4(p_variant.vector4_value.x, p_variant.vector4_value.y, p_variant.vector4_value.z, p_variant.vector4_value.w));",
        "        case MANAGED_VARIANT_TYPE_VECTOR4I:",
        "            return Variant(Vector4i(p_variant.vector4i_value.x, p_variant.vector4i_value.y, p_variant.vector4i_value.z, p_variant.vector4i_value.w));",
        "        case MANAGED_VARIANT_TYPE_PLANE:",
        "            return Variant(Plane(Vector3(p_variant.plane_value.normal.x, p_variant.plane_value.normal.y, p_variant.plane_value.normal.z), p_variant.plane_value.d));",
        "        case MANAGED_VARIANT_TYPE_QUATERNION:",
        "            return Variant(Quaternion(p_variant.quaternion_value.x, p_variant.quaternion_value.y, p_variant.quaternion_value.z, p_variant.quaternion_value.w));",
        "        case MANAGED_VARIANT_TYPE_AABB:",
        "            return Variant(AABB(Vector3(p_variant.aabb_value.position.x, p_variant.aabb_value.position.y, p_variant.aabb_value.position.z), Vector3(p_variant.aabb_value.size.x, p_variant.aabb_value.size.y, p_variant.aabb_value.size.z)));",
        "        case MANAGED_VARIANT_TYPE_BASIS:",
        "            return Variant(Basis(Vector3(p_variant.basis_value.x.x, p_variant.basis_value.x.y, p_variant.basis_value.x.z), Vector3(p_variant.basis_value.y.x, p_variant.basis_value.y.y, p_variant.basis_value.y.z), Vector3(p_variant.basis_value.z.x, p_variant.basis_value.z.y, p_variant.basis_value.z.z)));",
        "        case MANAGED_VARIANT_TYPE_TRANSFORM3D:",
        "            return Variant(Transform3D(Basis(Vector3(p_variant.transform3d_value.basis.x.x, p_variant.transform3d_value.basis.x.y, p_variant.transform3d_value.basis.x.z), Vector3(p_variant.transform3d_value.basis.y.x, p_variant.transform3d_value.basis.y.y, p_variant.transform3d_value.basis.y.z), Vector3(p_variant.transform3d_value.basis.z.x, p_variant.transform3d_value.basis.z.y, p_variant.transform3d_value.basis.z.z)), Vector3(p_variant.transform3d_value.origin.x, p_variant.transform3d_value.origin.y, p_variant.transform3d_value.origin.z)));",
        "        case MANAGED_VARIANT_TYPE_PROJECTION:",
        "            return Variant(Projection(Vector4(p_variant.projection_value.x.x, p_variant.projection_value.x.y, p_variant.projection_value.x.z, p_variant.projection_value.x.w), Vector4(p_variant.projection_value.y.x, p_variant.projection_value.y.y, p_variant.projection_value.y.z, p_variant.projection_value.y.w), Vector4(p_variant.projection_value.z.x, p_variant.projection_value.z.y, p_variant.projection_value.z.z, p_variant.projection_value.z.w), Vector4(p_variant.projection_value.w.x, p_variant.projection_value.w.y, p_variant.projection_value.w.z, p_variant.projection_value.w.w)));",
        "        case MANAGED_VARIANT_TYPE_COLOR:",
        "            return Variant(Color(p_variant.color_value.r, p_variant.color_value.g, p_variant.color_value.b, p_variant.color_value.a));",
        "        case MANAGED_VARIANT_TYPE_OBJECT:",
        "            return Variant(reinterpret_cast<Object*>(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_ARRAY:",
        "            return Variant(opaque_value_arg<Array>(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_DICTIONARY:",
        "            return Variant(opaque_value_arg<Dictionary>(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_CALLABLE:",
        "            return Variant(opaque_value_arg<Callable>(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_SIGNAL:",
        "            return Variant(opaque_value_arg<Signal>(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_PACKED_BYTE_ARRAY:",
        "            return Variant(opaque_value_arg<PackedByteArray>(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_PACKED_INT32_ARRAY:",
        "            return Variant(opaque_value_arg<PackedInt32Array>(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_PACKED_INT64_ARRAY:",
        "            return Variant(opaque_value_arg<PackedInt64Array>(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_PACKED_FLOAT32_ARRAY:",
        "            return Variant(opaque_value_arg<PackedFloat32Array>(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_PACKED_FLOAT64_ARRAY:",
        "            return Variant(opaque_value_arg<PackedFloat64Array>(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_PACKED_STRING_ARRAY:",
        "            return Variant(packed_string_array_arg(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_PACKED_VECTOR2_ARRAY:",
        "            return Variant(opaque_value_arg<PackedVector2Array>(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_PACKED_VECTOR3_ARRAY:",
        "            return Variant(opaque_value_arg<PackedVector3Array>(p_variant.native_ptr));",
        "        case MANAGED_VARIANT_TYPE_PACKED_COLOR_ARRAY:",
        "            return Variant(opaque_value_arg<PackedColorArray>(p_variant.native_ptr));",
        "        default:",
        "            return Variant();",
        "    }",
        "}",
        "",
        "void append_managed_varargs(Array& r_args, leanclr::vm::RtArray* p_varargs)",
        "{",
        "    if (p_varargs == nullptr)",
        "    {",
        "        return;",
        "    }",
        "    const int32_t count = leanclr::vm::Array::get_array_length(p_varargs);",
        "    for (int32_t i = 0; i < count; ++i)",
        "    {",
        "        ManagedVariant value = leanclr::vm::Array::get_array_data_at<ManagedVariant>(p_varargs, i);",
        "        r_args.append(variant_arg(value));",
        "    }",
        "}",
        "",
        "intptr_t new_packed_string_array(const PackedStringArray& p_array)",
        "{",
        "    return reinterpret_cast<intptr_t>(memnew(PackedStringArray(p_array)));",
        "}",
        "",
        "PackedStringArray packed_string_array_arg(intptr_t p_array_ptr)",
        "{",
        "    return p_array_ptr != 0 ? *reinterpret_cast<const PackedStringArray*>(p_array_ptr) : PackedStringArray();",
        "}",
        "",
        "leanclr::RtResultVoid godot_opaquevalue_destroy(intptr_t p_value_ptr) noexcept",
        "{",
        "    if (p_value_ptr != 0)",
        "    {",
        "        OpaqueValue* opaque = reinterpret_cast<OpaqueValue*>(p_value_ptr);",
        "        if (opaque->destroy != nullptr && opaque->value != nullptr)",
        "        {",
        "            opaque->destroy(opaque->value);",
        "        }",
        "        memdelete(opaque);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "intptr_t godot_array_create() noexcept",
        "{",
        "    return new_opaque_value(Array());",
        "}",
        "",
        "Array* godot_array_ptr(intptr_t p_array_ptr)",
        "{",
        "    OpaqueValue* opaque = reinterpret_cast<OpaqueValue*>(p_array_ptr);",
        "    return opaque != nullptr ? reinterpret_cast<Array*>(opaque->value) : nullptr;",
        "}",
        "",
        "int32_t godot_array_size(intptr_t p_array_ptr) noexcept",
        "{",
        "    Array* array = godot_array_ptr(p_array_ptr);",
        "    return array != nullptr ? static_cast<int32_t>(array->size()) : 0;",
        "}",
        "",
        "ManagedVariant godot_array_get(intptr_t p_array_ptr, int32_t p_index) noexcept",
        "{",
        "    Array* array = godot_array_ptr(p_array_ptr);",
        "    if (array == nullptr || p_index < 0 || p_index >= array->size())",
        "    {",
        "        return to_managed_variant(Variant());",
        "    }",
        "    return to_managed_variant(array->get(p_index));",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_set(intptr_t p_array_ptr, int32_t p_index, ManagedVariant p_value) noexcept",
        "{",
        "    Array* array = godot_array_ptr(p_array_ptr);",
        "    if (array != nullptr && p_index >= 0 && p_index < array->size())",
        "    {",
        "        array->set(p_index, variant_arg(p_value));",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_add(intptr_t p_array_ptr, ManagedVariant p_value) noexcept",
        "{",
        "    Array* array = godot_array_ptr(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->append(variant_arg(p_value));",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_insert(intptr_t p_array_ptr, int32_t p_index, ManagedVariant p_value) noexcept",
        "{",
        "    Array* array = godot_array_ptr(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->insert(p_index, variant_arg(p_value));",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_removeat(intptr_t p_array_ptr, int32_t p_index) noexcept",
        "{",
        "    Array* array = godot_array_ptr(p_array_ptr);",
        "    if (array != nullptr && p_index >= 0 && p_index < array->size())",
        "    {",
        "        array->remove_at(p_index);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_clear(intptr_t p_array_ptr) noexcept",
        "{",
        "    Array* array = godot_array_ptr(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->clear();",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "bool godot_array_contains(intptr_t p_array_ptr, ManagedVariant p_value) noexcept",
        "{",
        "    Array* array = godot_array_ptr(p_array_ptr);",
        "    return array != nullptr && array->has(variant_arg(p_value));",
        "}",
        "",
        "int32_t godot_array_indexof(intptr_t p_array_ptr, ManagedVariant p_value) noexcept",
        "{",
        "    Array* array = godot_array_ptr(p_array_ptr);",
        "    return array != nullptr ? static_cast<int32_t>(array->find(variant_arg(p_value))) : -1;",
        "}",
        "",
        "intptr_t godot_dictionary_create() noexcept",
        "{",
        "    return new_opaque_value(Dictionary());",
        "}",
        "",
        "Dictionary* godot_dictionary_ptr(intptr_t p_dictionary_ptr)",
        "{",
        "    OpaqueValue* opaque = reinterpret_cast<OpaqueValue*>(p_dictionary_ptr);",
        "    return opaque != nullptr ? reinterpret_cast<Dictionary*>(opaque->value) : nullptr;",
        "}",
        "",
        "int32_t godot_dictionary_size(intptr_t p_dictionary_ptr) noexcept",
        "{",
        "    Dictionary* dictionary = godot_dictionary_ptr(p_dictionary_ptr);",
        "    return dictionary != nullptr ? static_cast<int32_t>(dictionary->size()) : 0;",
        "}",
        "",
        "bool godot_dictionary_containskey(intptr_t p_dictionary_ptr, ManagedVariant p_key) noexcept",
        "{",
        "    Dictionary* dictionary = godot_dictionary_ptr(p_dictionary_ptr);",
        "    return dictionary != nullptr && dictionary->has(variant_arg(p_key));",
        "}",
        "",
        "ManagedVariant godot_dictionary_get(intptr_t p_dictionary_ptr, ManagedVariant p_key) noexcept",
        "{",
        "    Dictionary* dictionary = godot_dictionary_ptr(p_dictionary_ptr);",
        "    if (dictionary == nullptr)",
        "    {",
        "        return to_managed_variant(Variant());",
        "    }",
        "    const Variant key = variant_arg(p_key);",
        "    return dictionary->has(key) ? to_managed_variant((*dictionary)[key]) : to_managed_variant(Variant());",
        "}",
        "",
        "leanclr::RtResultVoid godot_dictionary_set(intptr_t p_dictionary_ptr, ManagedVariant p_key, ManagedVariant p_value) noexcept",
        "{",
        "    Dictionary* dictionary = godot_dictionary_ptr(p_dictionary_ptr);",
        "    if (dictionary != nullptr)",
        "    {",
        "        (*dictionary)[variant_arg(p_key)] = variant_arg(p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "bool godot_dictionary_remove(intptr_t p_dictionary_ptr, ManagedVariant p_key) noexcept",
        "{",
        "    Dictionary* dictionary = godot_dictionary_ptr(p_dictionary_ptr);",
        "    if (dictionary == nullptr)",
        "    {",
        "        return false;",
        "    }",
        "    const Variant key = variant_arg(p_key);",
        "    const bool had_key = dictionary->has(key);",
        "    if (had_key)",
        "    {",
        "        dictionary->erase(key);",
        "    }",
        "    return had_key;",
        "}",
        "",
        "leanclr::RtResultVoid godot_dictionary_clear(intptr_t p_dictionary_ptr) noexcept",
        "{",
        "    Dictionary* dictionary = godot_dictionary_ptr(p_dictionary_ptr);",
        "    if (dictionary != nullptr)",
        "    {",
        "        dictionary->clear();",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "intptr_t godot_dictionary_keys(intptr_t p_dictionary_ptr) noexcept",
        "{",
        "    Dictionary* dictionary = godot_dictionary_ptr(p_dictionary_ptr);",
        "    return new_opaque_value(dictionary != nullptr ? dictionary->keys() : Array());",
        "}",
        "",
        "intptr_t godot_dictionary_values(intptr_t p_dictionary_ptr) noexcept",
        "{",
        "    Dictionary* dictionary = godot_dictionary_ptr(p_dictionary_ptr);",
        "    return new_opaque_value(dictionary != nullptr ? dictionary->values() : Array());",
        "}",
        "",
        "leanclr::vm::RtString* godot_variant_stringify(ManagedVariant p_variant) noexcept",
        "{",
        "    return to_rt_string(variant_arg(p_variant).stringify());",
        "}",
        "",        "intptr_t godot_callable_create(intptr_t p_target_ptr, leanclr::vm::RtString* p_method) noexcept",
        "{",
        "    return new_opaque_value(Callable(reinterpret_cast<Object*>(p_target_ptr), StringName(rt_string_to_godot(p_method))));",
        "}",
        "",
        "bool godot_callable_isvalid(intptr_t p_callable_ptr) noexcept",
        "{",
        "    return opaque_value_arg<Callable>(p_callable_ptr).is_valid();",
        "}",
        "",
        "leanclr::vm::RtString* godot_callable_getmethod(intptr_t p_callable_ptr) noexcept",
        "{",
        "    return to_rt_string(opaque_value_arg<Callable>(p_callable_ptr).get_method());",
        "}",
        "",
        "ManagedVariant godot_callable_call(intptr_t p_callable_ptr, leanclr::vm::RtArray* p_varargs) noexcept",
        "{",
        "    Array args;",
        "    append_managed_varargs(args, p_varargs);",
        "    return to_managed_variant(opaque_value_arg<Callable>(p_callable_ptr).callv(args));",
        "}",
        "",
        "intptr_t godot_callable_bind(intptr_t p_callable_ptr, leanclr::vm::RtArray* p_varargs) noexcept",
        "{",
        "    Array args;",
        "    append_managed_varargs(args, p_varargs);",
        "    return new_opaque_value(opaque_value_arg<Callable>(p_callable_ptr).bindv(args));",
        "}",
        "",
        "intptr_t godot_signal_create(intptr_t p_target_ptr, leanclr::vm::RtString* p_signal) noexcept",
        "{",
        "    return new_opaque_value(Signal(reinterpret_cast<Object*>(p_target_ptr), StringName(rt_string_to_godot(p_signal))));",
        "}",
        "",
        "bool godot_signal_isnull(intptr_t p_signal_ptr) noexcept",
        "{",
        "    return opaque_value_arg<Signal>(p_signal_ptr).is_null();",
        "}",
        "",
        "leanclr::vm::RtString* godot_signal_getname(intptr_t p_signal_ptr) noexcept",
        "{",
        "    return to_rt_string(opaque_value_arg<Signal>(p_signal_ptr).get_name());",
        "}",
        "",
        "int32_t godot_signal_connect(intptr_t p_signal_ptr, intptr_t p_callable_ptr, int32_t p_flags) noexcept",
        "{",
        "    return static_cast<int32_t>(opaque_value_arg<Signal>(p_signal_ptr).connect(opaque_value_arg<Callable>(p_callable_ptr), p_flags));",
        "}",
        "",
        "leanclr::RtResultVoid godot_signal_emit(intptr_t p_signal_ptr, leanclr::vm::RtArray* p_varargs) noexcept",
        "{",
        "    Signal signal = opaque_value_arg<Signal>(p_signal_ptr);",
        "    Object* target = signal.get_object();",
        "    if (target != nullptr)",
        "    {",
        "        Array args;",
        "        args.append(Variant(signal.get_name()));",
        "        append_managed_varargs(args, p_varargs);",
        "        target->callv(StringName(\"emit_signal\"), args);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "intptr_t godot_packedstringarray_create() noexcept",
        "{",
        "    return new_packed_string_array(PackedStringArray());",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedstringarray_destroy(intptr_t p_array_ptr) noexcept",
        "{",
        "    if (p_array_ptr != 0)",
        "    {",
        "        memdelete(reinterpret_cast<PackedStringArray*>(p_array_ptr));",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "int32_t godot_packedstringarray_size(intptr_t p_array_ptr) noexcept",
        "{",
        "    return static_cast<int32_t>(packed_string_array_arg(p_array_ptr).size());",
        "}",
        "",
        "leanclr::vm::RtString* godot_packedstringarray_get(intptr_t p_array_ptr, int32_t p_index) noexcept",
        "{",
        "    const PackedStringArray array = packed_string_array_arg(p_array_ptr);",
        "    if (p_index < 0 || p_index >= array.size())",
        "    {",
        "        return leanclr::vm::String::get_empty_string();",
        "    }",
        "    return to_rt_string(array.get(p_index));",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedstringarray_append(intptr_t p_array_ptr, leanclr::vm::RtString* p_value) noexcept",
        "{",
        "    PackedStringArray* array = reinterpret_cast<PackedStringArray*>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->append(rt_string_to_godot(p_value));",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "intptr_t godot_packedbytearray_create() noexcept",
        "{",
        "    return new_opaque_value(PackedByteArray());",
        "}",
        "",
        "int32_t godot_packedbytearray_size(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedByteArray* array = opaque_value_ptr<PackedByteArray>(p_array_ptr);",
        "    return array != nullptr ? static_cast<int32_t>(array->size()) : 0;",
        "}",
        "",
        "uint8_t godot_packedbytearray_get(intptr_t p_array_ptr, int32_t p_index) noexcept",
        "{",
        "    PackedByteArray* array = opaque_value_ptr<PackedByteArray>(p_array_ptr);",
        "    return array != nullptr && p_index >= 0 && p_index < array->size() ? array->get(p_index) : 0;",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedbytearray_set(intptr_t p_array_ptr, int32_t p_index, uint8_t p_value) noexcept",
        "{",
        "    PackedByteArray* array = opaque_value_ptr<PackedByteArray>(p_array_ptr);",
        "    if (array != nullptr && p_index >= 0 && p_index < array->size())",
        "    {",
        "        array->set(p_index, p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedbytearray_add(intptr_t p_array_ptr, uint8_t p_value) noexcept",
        "{",
        "    PackedByteArray* array = opaque_value_ptr<PackedByteArray>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->append(p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedbytearray_clear(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedByteArray* array = opaque_value_ptr<PackedByteArray>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->clear();",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedbytearray_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_params;",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedbytearray_create());",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedbytearray_size_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedbytearray_size(p_array_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedbytearray_get_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedbytearray_get(p_array_ptr, p_index));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedbytearray_set_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    uint8_t p_value = leanclr::interp::EvalStackOp::get_param<uint8_t>(p_params, 2);",
        "    return godot_packedbytearray_set(p_array_ptr, p_index, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedbytearray_add_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    uint8_t p_value = leanclr::interp::EvalStackOp::get_param<uint8_t>(p_params, 1);",
        "    return godot_packedbytearray_add(p_array_ptr, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedbytearray_clear_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_packedbytearray_clear(p_array_ptr);",
        "}",
        "",
        "intptr_t godot_packedint32array_create() noexcept",
        "{",
        "    return new_opaque_value(PackedInt32Array());",
        "}",
        "",
        "int32_t godot_packedint32array_size(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedInt32Array* array = opaque_value_ptr<PackedInt32Array>(p_array_ptr);",
        "    return array != nullptr ? static_cast<int32_t>(array->size()) : 0;",
        "}",
        "",
        "int32_t godot_packedint32array_get(intptr_t p_array_ptr, int32_t p_index) noexcept",
        "{",
        "    PackedInt32Array* array = opaque_value_ptr<PackedInt32Array>(p_array_ptr);",
        "    return array != nullptr && p_index >= 0 && p_index < array->size() ? array->get(p_index) : 0;",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint32array_set(intptr_t p_array_ptr, int32_t p_index, int32_t p_value) noexcept",
        "{",
        "    PackedInt32Array* array = opaque_value_ptr<PackedInt32Array>(p_array_ptr);",
        "    if (array != nullptr && p_index >= 0 && p_index < array->size())",
        "    {",
        "        array->set(p_index, p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint32array_add(intptr_t p_array_ptr, int32_t p_value) noexcept",
        "{",
        "    PackedInt32Array* array = opaque_value_ptr<PackedInt32Array>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->append(p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint32array_clear(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedInt32Array* array = opaque_value_ptr<PackedInt32Array>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->clear();",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint32array_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_params;",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedint32array_create());",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint32array_size_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedint32array_size(p_array_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint32array_get_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedint32array_get(p_array_ptr, p_index));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint32array_set_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    int32_t p_value = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 2);",
        "    return godot_packedint32array_set(p_array_ptr, p_index, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint32array_add_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    int32_t p_value = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    return godot_packedint32array_add(p_array_ptr, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint32array_clear_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_packedint32array_clear(p_array_ptr);",
        "}",
        "",
        "intptr_t godot_packedint64array_create() noexcept",
        "{",
        "    return new_opaque_value(PackedInt64Array());",
        "}",
        "",
        "int32_t godot_packedint64array_size(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedInt64Array* array = opaque_value_ptr<PackedInt64Array>(p_array_ptr);",
        "    return array != nullptr ? static_cast<int32_t>(array->size()) : 0;",
        "}",
        "",
        "int64_t godot_packedint64array_get(intptr_t p_array_ptr, int32_t p_index) noexcept",
        "{",
        "    PackedInt64Array* array = opaque_value_ptr<PackedInt64Array>(p_array_ptr);",
        "    return array != nullptr && p_index >= 0 && p_index < array->size() ? array->get(p_index) : 0;",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint64array_set(intptr_t p_array_ptr, int32_t p_index, int64_t p_value) noexcept",
        "{",
        "    PackedInt64Array* array = opaque_value_ptr<PackedInt64Array>(p_array_ptr);",
        "    if (array != nullptr && p_index >= 0 && p_index < array->size())",
        "    {",
        "        array->set(p_index, p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint64array_add(intptr_t p_array_ptr, int64_t p_value) noexcept",
        "{",
        "    PackedInt64Array* array = opaque_value_ptr<PackedInt64Array>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->append(p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint64array_clear(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedInt64Array* array = opaque_value_ptr<PackedInt64Array>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->clear();",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint64array_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_params;",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedint64array_create());",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint64array_size_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedint64array_size(p_array_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint64array_get_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedint64array_get(p_array_ptr, p_index));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint64array_set_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    int64_t p_value = leanclr::interp::EvalStackOp::get_param<int64_t>(p_params, 2);",
        "    return godot_packedint64array_set(p_array_ptr, p_index, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint64array_add_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    int64_t p_value = leanclr::interp::EvalStackOp::get_param<int64_t>(p_params, 1);",
        "    return godot_packedint64array_add(p_array_ptr, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedint64array_clear_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_packedint64array_clear(p_array_ptr);",
        "}",
        "",
        "intptr_t godot_packedfloat32array_create() noexcept",
        "{",
        "    return new_opaque_value(PackedFloat32Array());",
        "}",
        "",
        "int32_t godot_packedfloat32array_size(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedFloat32Array* array = opaque_value_ptr<PackedFloat32Array>(p_array_ptr);",
        "    return array != nullptr ? static_cast<int32_t>(array->size()) : 0;",
        "}",
        "",
        "float godot_packedfloat32array_get(intptr_t p_array_ptr, int32_t p_index) noexcept",
        "{",
        "    PackedFloat32Array* array = opaque_value_ptr<PackedFloat32Array>(p_array_ptr);",
        "    return array != nullptr && p_index >= 0 && p_index < array->size() ? array->get(p_index) : 0.0f;",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat32array_set(intptr_t p_array_ptr, int32_t p_index, float p_value) noexcept",
        "{",
        "    PackedFloat32Array* array = opaque_value_ptr<PackedFloat32Array>(p_array_ptr);",
        "    if (array != nullptr && p_index >= 0 && p_index < array->size())",
        "    {",
        "        array->set(p_index, p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat32array_add(intptr_t p_array_ptr, float p_value) noexcept",
        "{",
        "    PackedFloat32Array* array = opaque_value_ptr<PackedFloat32Array>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->append(p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat32array_clear(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedFloat32Array* array = opaque_value_ptr<PackedFloat32Array>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->clear();",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat32array_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_params;",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedfloat32array_create());",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat32array_size_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedfloat32array_size(p_array_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat32array_get_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedfloat32array_get(p_array_ptr, p_index));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat32array_set_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    float p_value = leanclr::interp::EvalStackOp::get_param<float>(p_params, 2);",
        "    return godot_packedfloat32array_set(p_array_ptr, p_index, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat32array_add_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    float p_value = leanclr::interp::EvalStackOp::get_param<float>(p_params, 1);",
        "    return godot_packedfloat32array_add(p_array_ptr, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat32array_clear_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_packedfloat32array_clear(p_array_ptr);",
        "}",
        "",
        "intptr_t godot_packedfloat64array_create() noexcept",
        "{",
        "    return new_opaque_value(PackedFloat64Array());",
        "}",
        "",
        "int32_t godot_packedfloat64array_size(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedFloat64Array* array = opaque_value_ptr<PackedFloat64Array>(p_array_ptr);",
        "    return array != nullptr ? static_cast<int32_t>(array->size()) : 0;",
        "}",
        "",
        "double godot_packedfloat64array_get(intptr_t p_array_ptr, int32_t p_index) noexcept",
        "{",
        "    PackedFloat64Array* array = opaque_value_ptr<PackedFloat64Array>(p_array_ptr);",
        "    return array != nullptr && p_index >= 0 && p_index < array->size() ? array->get(p_index) : 0.0;",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat64array_set(intptr_t p_array_ptr, int32_t p_index, double p_value) noexcept",
        "{",
        "    PackedFloat64Array* array = opaque_value_ptr<PackedFloat64Array>(p_array_ptr);",
        "    if (array != nullptr && p_index >= 0 && p_index < array->size())",
        "    {",
        "        array->set(p_index, p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat64array_add(intptr_t p_array_ptr, double p_value) noexcept",
        "{",
        "    PackedFloat64Array* array = opaque_value_ptr<PackedFloat64Array>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->append(p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat64array_clear(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedFloat64Array* array = opaque_value_ptr<PackedFloat64Array>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->clear();",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat64array_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_params;",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedfloat64array_create());",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat64array_size_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedfloat64array_size(p_array_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat64array_get_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedfloat64array_get(p_array_ptr, p_index));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat64array_set_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    double p_value = leanclr::interp::EvalStackOp::get_param<double>(p_params, 2);",
        "    return godot_packedfloat64array_set(p_array_ptr, p_index, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat64array_add_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    double p_value = leanclr::interp::EvalStackOp::get_param<double>(p_params, 1);",
        "    return godot_packedfloat64array_add(p_array_ptr, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedfloat64array_clear_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_packedfloat64array_clear(p_array_ptr);",
        "}",
        "",
        "intptr_t godot_packedvector2array_create() noexcept",
        "{",
        "    return new_opaque_value(PackedVector2Array());",
        "}",
        "",
        "int32_t godot_packedvector2array_size(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedVector2Array* array = opaque_value_ptr<PackedVector2Array>(p_array_ptr);",
        "    return array != nullptr ? static_cast<int32_t>(array->size()) : 0;",
        "}",
        "",
        "Vector2 godot_packedvector2array_get(intptr_t p_array_ptr, int32_t p_index) noexcept",
        "{",
        "    PackedVector2Array* array = opaque_value_ptr<PackedVector2Array>(p_array_ptr);",
        "    return array != nullptr && p_index >= 0 && p_index < array->size() ? array->get(p_index) : Vector2();",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector2array_set(intptr_t p_array_ptr, int32_t p_index, Vector2 p_value) noexcept",
        "{",
        "    PackedVector2Array* array = opaque_value_ptr<PackedVector2Array>(p_array_ptr);",
        "    if (array != nullptr && p_index >= 0 && p_index < array->size())",
        "    {",
        "        array->set(p_index, p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector2array_add(intptr_t p_array_ptr, Vector2 p_value) noexcept",
        "{",
        "    PackedVector2Array* array = opaque_value_ptr<PackedVector2Array>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->append(p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector2array_clear(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedVector2Array* array = opaque_value_ptr<PackedVector2Array>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->clear();",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector2array_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_params;",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedvector2array_create());",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector2array_size_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedvector2array_size(p_array_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector2array_get_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedvector2array_get(p_array_ptr, p_index));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector2array_set_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    Vector2 p_value = leanclr::interp::EvalStackOp::get_param<Vector2>(p_params, 2);",
        "    return godot_packedvector2array_set(p_array_ptr, p_index, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector2array_add_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    Vector2 p_value = leanclr::interp::EvalStackOp::get_param<Vector2>(p_params, 1);",
        "    return godot_packedvector2array_add(p_array_ptr, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector2array_clear_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_packedvector2array_clear(p_array_ptr);",
        "}",
        "",
        "intptr_t godot_packedvector3array_create() noexcept",
        "{",
        "    return new_opaque_value(PackedVector3Array());",
        "}",
        "",
        "int32_t godot_packedvector3array_size(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedVector3Array* array = opaque_value_ptr<PackedVector3Array>(p_array_ptr);",
        "    return array != nullptr ? static_cast<int32_t>(array->size()) : 0;",
        "}",
        "",
        "Vector3 godot_packedvector3array_get(intptr_t p_array_ptr, int32_t p_index) noexcept",
        "{",
        "    PackedVector3Array* array = opaque_value_ptr<PackedVector3Array>(p_array_ptr);",
        "    return array != nullptr && p_index >= 0 && p_index < array->size() ? array->get(p_index) : Vector3();",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector3array_set(intptr_t p_array_ptr, int32_t p_index, Vector3 p_value) noexcept",
        "{",
        "    PackedVector3Array* array = opaque_value_ptr<PackedVector3Array>(p_array_ptr);",
        "    if (array != nullptr && p_index >= 0 && p_index < array->size())",
        "    {",
        "        array->set(p_index, p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector3array_add(intptr_t p_array_ptr, Vector3 p_value) noexcept",
        "{",
        "    PackedVector3Array* array = opaque_value_ptr<PackedVector3Array>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->append(p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector3array_clear(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedVector3Array* array = opaque_value_ptr<PackedVector3Array>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->clear();",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector3array_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_params;",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedvector3array_create());",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector3array_size_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedvector3array_size(p_array_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector3array_get_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedvector3array_get(p_array_ptr, p_index));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector3array_set_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    Vector3 p_value = leanclr::interp::EvalStackOp::get_param<Vector3>(p_params, 2);",
        "    return godot_packedvector3array_set(p_array_ptr, p_index, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector3array_add_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    Vector3 p_value = leanclr::interp::EvalStackOp::get_param<Vector3>(p_params, 1);",
        "    return godot_packedvector3array_add(p_array_ptr, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedvector3array_clear_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_packedvector3array_clear(p_array_ptr);",
        "}",
        "",
        "intptr_t godot_packedcolorarray_create() noexcept",
        "{",
        "    return new_opaque_value(PackedColorArray());",
        "}",
        "",
        "int32_t godot_packedcolorarray_size(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedColorArray* array = opaque_value_ptr<PackedColorArray>(p_array_ptr);",
        "    return array != nullptr ? static_cast<int32_t>(array->size()) : 0;",
        "}",
        "",
        "Color godot_packedcolorarray_get(intptr_t p_array_ptr, int32_t p_index) noexcept",
        "{",
        "    PackedColorArray* array = opaque_value_ptr<PackedColorArray>(p_array_ptr);",
        "    return array != nullptr && p_index >= 0 && p_index < array->size() ? array->get(p_index) : Color();",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedcolorarray_set(intptr_t p_array_ptr, int32_t p_index, Color p_value) noexcept",
        "{",
        "    PackedColorArray* array = opaque_value_ptr<PackedColorArray>(p_array_ptr);",
        "    if (array != nullptr && p_index >= 0 && p_index < array->size())",
        "    {",
        "        array->set(p_index, p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedcolorarray_add(intptr_t p_array_ptr, Color p_value) noexcept",
        "{",
        "    PackedColorArray* array = opaque_value_ptr<PackedColorArray>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->append(p_value);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedcolorarray_clear(intptr_t p_array_ptr) noexcept",
        "{",
        "    PackedColorArray* array = opaque_value_ptr<PackedColorArray>(p_array_ptr);",
        "    if (array != nullptr)",
        "    {",
        "        array->clear();",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedcolorarray_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_params;",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedcolorarray_create());",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedcolorarray_size_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedcolorarray_size(p_array_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedcolorarray_get_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedcolorarray_get(p_array_ptr, p_index));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedcolorarray_set_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    Color p_value = leanclr::interp::EvalStackOp::get_param<Color>(p_params, 2);",
        "    return godot_packedcolorarray_set(p_array_ptr, p_index, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedcolorarray_add_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    Color p_value = leanclr::interp::EvalStackOp::get_param<Color>(p_params, 1);",
        "    return godot_packedcolorarray_add(p_array_ptr, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedcolorarray_clear_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr, const leanclr::metadata::RtMethodInfo* p_method, const leanclr::interp::RtStackObject* p_params, leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_packedcolorarray_clear(p_array_ptr);",
        "}",
        "",
        "leanclr::RtResultVoid godot_variant_stringify_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    ManagedVariant p_variant = leanclr::interp::EvalStackOp::get_param<ManagedVariant>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_variant_stringify(p_variant));",
        "    return leanclr::core::Unit{};",
        "}",
        "",        "leanclr::RtResultVoid godot_callable_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_target_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::vm::RtString* p_method_name = leanclr::interp::EvalStackOp::get_param<leanclr::vm::RtString*>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_callable_create(p_target_ptr, p_method_name));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_callable_isvalid_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_callable_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_callable_isvalid(p_callable_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_callable_getmethod_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_callable_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_callable_getmethod(p_callable_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_callable_call_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_callable_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::vm::RtArray* p_varargs = leanclr::interp::EvalStackOp::get_param<leanclr::vm::RtArray*>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_callable_call(p_callable_ptr, p_varargs));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_callable_bind_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_callable_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::vm::RtArray* p_varargs = leanclr::interp::EvalStackOp::get_param<leanclr::vm::RtArray*>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_callable_bind(p_callable_ptr, p_varargs));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_signal_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_target_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::vm::RtString* p_signal_name = leanclr::interp::EvalStackOp::get_param<leanclr::vm::RtString*>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_signal_create(p_target_ptr, p_signal_name));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_signal_isnull_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_signal_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_signal_isnull(p_signal_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_signal_getname_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_signal_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_signal_getname(p_signal_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_signal_connect_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_signal_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const intptr_t p_callable_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 1);",
        "    const int32_t p_flags = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 2);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_signal_connect(p_signal_ptr, p_callable_ptr, p_flags));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_signal_emit_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_signal_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::vm::RtArray* p_varargs = leanclr::interp::EvalStackOp::get_param<leanclr::vm::RtArray*>(p_params, 1);",
        "    return godot_signal_emit(p_signal_ptr, p_varargs);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedstringarray_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_params;",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedstringarray_create());",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedstringarray_destroy_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_packedstringarray_destroy(p_array_ptr);",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedstringarray_size_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedstringarray_size(p_array_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedstringarray_get_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_packedstringarray_get(p_array_ptr, p_index));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_packedstringarray_append_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::vm::RtString* p_value = leanclr::interp::EvalStackOp::get_param<leanclr::vm::RtString*>(p_params, 1);",
        "    return godot_packedstringarray_append(p_array_ptr, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_opaquevalue_destroy_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_value_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_opaquevalue_destroy(p_value_ptr);",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_params;",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_array_create());",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_size_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_array_size(p_array_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_get_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_array_get(p_array_ptr, p_index));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_set_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    ManagedVariant p_value = leanclr::interp::EvalStackOp::get_param<ManagedVariant>(p_params, 2);",
        "    return godot_array_set(p_array_ptr, p_index, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_add_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    ManagedVariant p_value = leanclr::interp::EvalStackOp::get_param<ManagedVariant>(p_params, 1);",
        "    return godot_array_add(p_array_ptr, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_insert_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    ManagedVariant p_value = leanclr::interp::EvalStackOp::get_param<ManagedVariant>(p_params, 2);",
        "    return godot_array_insert(p_array_ptr, p_index, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_removeat_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    const int32_t p_index = leanclr::interp::EvalStackOp::get_param<int32_t>(p_params, 1);",
        "    return godot_array_removeat(p_array_ptr, p_index);",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_clear_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_array_clear(p_array_ptr);",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_contains_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    ManagedVariant p_value = leanclr::interp::EvalStackOp::get_param<ManagedVariant>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_array_contains(p_array_ptr, p_value));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_array_indexof_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_array_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    ManagedVariant p_value = leanclr::interp::EvalStackOp::get_param<ManagedVariant>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_array_indexof(p_array_ptr, p_value));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_dictionary_create_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_params;",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_dictionary_create());",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_dictionary_size_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_dictionary_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_dictionary_size(p_dictionary_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_dictionary_containskey_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_dictionary_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    ManagedVariant p_key = leanclr::interp::EvalStackOp::get_param<ManagedVariant>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_dictionary_containskey(p_dictionary_ptr, p_key));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_dictionary_get_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_dictionary_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    ManagedVariant p_key = leanclr::interp::EvalStackOp::get_param<ManagedVariant>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_dictionary_get(p_dictionary_ptr, p_key));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_dictionary_set_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_dictionary_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    ManagedVariant p_key = leanclr::interp::EvalStackOp::get_param<ManagedVariant>(p_params, 1);",
        "    ManagedVariant p_value = leanclr::interp::EvalStackOp::get_param<ManagedVariant>(p_params, 10);",
        "    return godot_dictionary_set(p_dictionary_ptr, p_key, p_value);",
        "}",
        "",
        "leanclr::RtResultVoid godot_dictionary_remove_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_dictionary_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    ManagedVariant p_key = leanclr::interp::EvalStackOp::get_param<ManagedVariant>(p_params, 1);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_dictionary_remove(p_dictionary_ptr, p_key));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_dictionary_clear_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_dictionary_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_dictionary_clear(p_dictionary_ptr);",
        "}",
        "",
        "leanclr::RtResultVoid godot_dictionary_keys_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_dictionary_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_dictionary_keys(p_dictionary_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_dictionary_values_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    const intptr_t p_dictionary_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    leanclr::interp::EvalStackOp::set_return(p_ret, godot_dictionary_values(p_dictionary_ptr));",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "template <typename T>",
        "T* as_godot_object(intptr_t p_native_ptr)",
        "{",
        "    return Object::cast_to<T>(reinterpret_cast<Object*>(p_native_ptr));",
        "}",
        "",
        "template <typename T>",
        "intptr_t retain_refcounted(const Ref<T>& p_ref)",
        "{",
        "    T* ptr = p_ref.ptr();",
        "    if (ptr != nullptr)",
        "    {",
        "        ptr->reference();",
        "    }",
        "    return reinterpret_cast<intptr_t>(ptr);",
        "}",
        "",
        "leanclr::RtResultVoid godot_object_releaserefcounted(intptr_t p_native_ptr) noexcept",
        "{",
        "    RefCounted* ref_counted = as_godot_object<RefCounted>(p_native_ptr);",
        "    if (ref_counted != nullptr && ref_counted->unreference())",
        "    {",
        "        memdelete(ref_counted);",
        "    }",
        "    return leanclr::core::Unit{};",
        "}",
        "",
        "leanclr::RtResultVoid godot_object_releaserefcounted_invoker(leanclr::metadata::RtManagedMethodPointer p_method_ptr,",
        "                                       const leanclr::metadata::RtMethodInfo* p_method,",
        "                                       const leanclr::interp::RtStackObject* p_params,",
        "                                       leanclr::interp::RtStackObject* p_ret) noexcept",
        "{",
        "    (void)p_method_ptr;",
        "    (void)p_method;",
        "    (void)p_ret;",
        "    const intptr_t p_native_ptr = leanclr::interp::EvalStackOp::get_param<intptr_t>(p_params, 0);",
        "    return godot_object_releaserefcounted(p_native_ptr);",
        "}",
        "",
    ]
    for method in methods:
        body.append(generate_native_method_function(method).rstrip())
        body.append("")
        body.append(generate_native_invoker(method).rstrip())
        body.append("")

    body.extend(["} // namespace", "", "void register_generated_godot_api_icalls()", "{"])
    body.extend(
        [
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotObjectReleaseRefCounted(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_object_releaserefcounted),",
            "                                                       godot_object_releaserefcounted_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotVariantStringify(Godot.Variant)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_variant_stringify),",
            "                                                       godot_variant_stringify_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotCallableCreate(System.IntPtr,System.String)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_callable_create),",
            "                                                       godot_callable_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotCallableIsValid(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_callable_isvalid),",
            "                                                       godot_callable_isvalid_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotCallableGetMethod(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_callable_getmethod),",
            "                                                       godot_callable_getmethod_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotCallableCall(System.IntPtr,Godot.Variant[])\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_callable_call),",
            "                                                       godot_callable_call_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotCallableBind(System.IntPtr,Godot.Variant[])\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_callable_bind),",
            "                                                       godot_callable_bind_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotSignalCreate(System.IntPtr,System.String)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_signal_create),",
            "                                                       godot_signal_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotSignalIsNull(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_signal_isnull),",
            "                                                       godot_signal_isnull_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotSignalGetName(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_signal_getname),",
            "                                                       godot_signal_getname_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotSignalConnect(System.IntPtr,System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_signal_connect),",
            "                                                       godot_signal_connect_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotSignalEmit(System.IntPtr,Godot.Variant[])\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_signal_emit),",
            "                                                       godot_signal_emit_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedStringArrayCreate()\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedstringarray_create),",
            "                                                       godot_packedstringarray_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedStringArrayDestroy(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedstringarray_destroy),",
            "                                                       godot_packedstringarray_destroy_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedStringArraySize(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedstringarray_size),",
            "                                                       godot_packedstringarray_size_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedStringArrayGet(System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedstringarray_get),",
            "                                                       godot_packedstringarray_get_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedStringArrayAppend(System.IntPtr,System.String)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedstringarray_append),",
            "                                                       godot_packedstringarray_append_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedByteArrayCreate()\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedbytearray_create),",
            "                                                       godot_packedbytearray_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedByteArraySize(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedbytearray_size),",
            "                                                       godot_packedbytearray_size_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedByteArrayGet(System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedbytearray_get),",
            "                                                       godot_packedbytearray_get_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedByteArraySet(System.IntPtr,System.Int32,System.Byte)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedbytearray_set),",
            "                                                       godot_packedbytearray_set_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedByteArrayAdd(System.IntPtr,System.Byte)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedbytearray_add),",
            "                                                       godot_packedbytearray_add_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedByteArrayClear(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedbytearray_clear),",
            "                                                       godot_packedbytearray_clear_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedInt32ArrayCreate()\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedint32array_create),",
            "                                                       godot_packedint32array_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedInt32ArraySize(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedint32array_size),",
            "                                                       godot_packedint32array_size_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedInt32ArrayGet(System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedint32array_get),",
            "                                                       godot_packedint32array_get_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedInt32ArraySet(System.IntPtr,System.Int32,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedint32array_set),",
            "                                                       godot_packedint32array_set_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedInt32ArrayAdd(System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedint32array_add),",
            "                                                       godot_packedint32array_add_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedInt32ArrayClear(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedint32array_clear),",
            "                                                       godot_packedint32array_clear_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedInt64ArrayCreate()\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedint64array_create),",
            "                                                       godot_packedint64array_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedInt64ArraySize(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedint64array_size),",
            "                                                       godot_packedint64array_size_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedInt64ArrayGet(System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedint64array_get),",
            "                                                       godot_packedint64array_get_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedInt64ArraySet(System.IntPtr,System.Int32,System.Int64)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedint64array_set),",
            "                                                       godot_packedint64array_set_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedInt64ArrayAdd(System.IntPtr,System.Int64)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedint64array_add),",
            "                                                       godot_packedint64array_add_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedInt64ArrayClear(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedint64array_clear),",
            "                                                       godot_packedint64array_clear_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedFloat32ArrayCreate()\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedfloat32array_create),",
            "                                                       godot_packedfloat32array_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedFloat32ArraySize(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedfloat32array_size),",
            "                                                       godot_packedfloat32array_size_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedFloat32ArrayGet(System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedfloat32array_get),",
            "                                                       godot_packedfloat32array_get_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedFloat32ArraySet(System.IntPtr,System.Int32,System.Single)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedfloat32array_set),",
            "                                                       godot_packedfloat32array_set_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedFloat32ArrayAdd(System.IntPtr,System.Single)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedfloat32array_add),",
            "                                                       godot_packedfloat32array_add_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedFloat32ArrayClear(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedfloat32array_clear),",
            "                                                       godot_packedfloat32array_clear_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedFloat64ArrayCreate()\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedfloat64array_create),",
            "                                                       godot_packedfloat64array_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedFloat64ArraySize(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedfloat64array_size),",
            "                                                       godot_packedfloat64array_size_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedFloat64ArrayGet(System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedfloat64array_get),",
            "                                                       godot_packedfloat64array_get_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedFloat64ArraySet(System.IntPtr,System.Int32,System.Double)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedfloat64array_set),",
            "                                                       godot_packedfloat64array_set_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedFloat64ArrayAdd(System.IntPtr,System.Double)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedfloat64array_add),",
            "                                                       godot_packedfloat64array_add_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedFloat64ArrayClear(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedfloat64array_clear),",
            "                                                       godot_packedfloat64array_clear_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedVector2ArrayCreate()\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedvector2array_create),",
            "                                                       godot_packedvector2array_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedVector2ArraySize(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedvector2array_size),",
            "                                                       godot_packedvector2array_size_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedVector2ArrayGet(System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedvector2array_get),",
            "                                                       godot_packedvector2array_get_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedVector2ArraySet(System.IntPtr,System.Int32,Godot.Vector2)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedvector2array_set),",
            "                                                       godot_packedvector2array_set_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedVector2ArrayAdd(System.IntPtr,Godot.Vector2)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedvector2array_add),",
            "                                                       godot_packedvector2array_add_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedVector2ArrayClear(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedvector2array_clear),",
            "                                                       godot_packedvector2array_clear_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedVector3ArrayCreate()\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedvector3array_create),",
            "                                                       godot_packedvector3array_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedVector3ArraySize(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedvector3array_size),",
            "                                                       godot_packedvector3array_size_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedVector3ArrayGet(System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedvector3array_get),",
            "                                                       godot_packedvector3array_get_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedVector3ArraySet(System.IntPtr,System.Int32,Godot.Vector3)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedvector3array_set),",
            "                                                       godot_packedvector3array_set_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedVector3ArrayAdd(System.IntPtr,Godot.Vector3)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedvector3array_add),",
            "                                                       godot_packedvector3array_add_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedVector3ArrayClear(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedvector3array_clear),",
            "                                                       godot_packedvector3array_clear_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedColorArrayCreate()\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedcolorarray_create),",
            "                                                       godot_packedcolorarray_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedColorArraySize(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedcolorarray_size),",
            "                                                       godot_packedcolorarray_size_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedColorArrayGet(System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedcolorarray_get),",
            "                                                       godot_packedcolorarray_get_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedColorArraySet(System.IntPtr,System.Int32,Godot.Color)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedcolorarray_set),",
            "                                                       godot_packedcolorarray_set_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedColorArrayAdd(System.IntPtr,Godot.Color)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedcolorarray_add),",
            "                                                       godot_packedcolorarray_add_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotPackedColorArrayClear(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_packedcolorarray_clear),",
            "                                                       godot_packedcolorarray_clear_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotOpaqueValueDestroy(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_opaquevalue_destroy),",
            "                                                       godot_opaquevalue_destroy_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotArrayCreate()\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_array_create),",
            "                                                       godot_array_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotArraySize(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_array_size),",
            "                                                       godot_array_size_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotArrayGet(System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_array_get),",
            "                                                       godot_array_get_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotArraySet(System.IntPtr,System.Int32,Godot.Variant)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_array_set),",
            "                                                       godot_array_set_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotArrayAdd(System.IntPtr,Godot.Variant)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_array_add),",
            "                                                       godot_array_add_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotArrayInsert(System.IntPtr,System.Int32,Godot.Variant)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_array_insert),",
            "                                                       godot_array_insert_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotArrayRemoveAt(System.IntPtr,System.Int32)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_array_removeat),",
            "                                                       godot_array_removeat_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotArrayClear(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_array_clear),",
            "                                                       godot_array_clear_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotArrayContains(System.IntPtr,Godot.Variant)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_array_contains),",
            "                                                       godot_array_contains_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotArrayIndexOf(System.IntPtr,Godot.Variant)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_array_indexof),",
            "                                                       godot_array_indexof_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotDictionaryCreate()\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_dictionary_create),",
            "                                                       godot_dictionary_create_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotDictionarySize(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_dictionary_size),",
            "                                                       godot_dictionary_size_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotDictionaryContainsKey(System.IntPtr,Godot.Variant)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_dictionary_containskey),",
            "                                                       godot_dictionary_containskey_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotDictionaryGet(System.IntPtr,Godot.Variant)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_dictionary_get),",
            "                                                       godot_dictionary_get_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotDictionarySet(System.IntPtr,Godot.Variant,Godot.Variant)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_dictionary_set),",
            "                                                       godot_dictionary_set_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotDictionaryRemove(System.IntPtr,Godot.Variant)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_dictionary_remove),",
            "                                                       godot_dictionary_remove_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotDictionaryClear(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_dictionary_clear),",
            "                                                       godot_dictionary_clear_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotDictionaryKeys(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_dictionary_keys),",
            "                                                       godot_dictionary_keys_invoker);",
            "    leanclr::vm::InternalCalls::register_internal_call(\"Godot.NativeCalls::GodotDictionaryValues(System.IntPtr)\",",
            "                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&godot_dictionary_values),",
            "                                                       godot_dictionary_values_invoker);",
        ]
    )
    for method in methods:
        fn = native_function_name(method)
        body.extend(
            [
                f"    leanclr::vm::InternalCalls::register_internal_call(\"{icall_name(method)}\",",
                f"                                                       reinterpret_cast<leanclr::vm::InternalCallFunction>(&{fn}),",
                f"                                                       {fn}_invoker);",
            ]
        )
    body.extend(["}", "", "} // namespace godot", ""])
    write(src_dir / "generated" / "godot_api.generated.cpp", "\n".join(body))


def generate_report(report, report_path):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def generate_summary_report(report, report_path):
    overview = report["overview"]
    top_types = sorted(report["unsupported_type_counts"].items(), key=lambda item: item[1], reverse=True)[:20]
    top_classes = sorted(
        (row for row in report["per_class"] if row["methods_generated"]),
        key=lambda row: row["methods_generated"],
        reverse=True,
    )[:20]
    lines = [
        "# LeanCLR Godot Binding Statistics",
        "",
        "## Overview",
        "",
        f"- API classes: {overview['api_class_count']}",
        f"- Generated C# skeleton classes: {overview['skeleton_class_count']} ({overview['class_skeleton_coverage_pct']}%)",
        f"- Native-bound classes with generated methods: {overview['native_bound_class_count']} ({overview['native_class_coverage_pct']}%)",
        f"- API methods: {overview['total_methods']}",
        f"- Generated methods: {overview['generated_methods']} ({overview['method_coverage_pct']}%)",
        f"- Generated native methods: {overview['generated_native_methods']}",
        f"- Generated vararg bridges: {overview['generated_vararg_bridges']}",
        f"- Generated virtual stubs: {overview['generated_virtual_stubs']}",
        f"- Skipped methods: {overview['skipped_methods']}",
        "",
        "## Skip Breakdown",
        "",
    ]
    for reason, count in sorted(report["skipped_methods"].items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {reason}: {count}")
    lines.extend(["", "## Top Unsupported Types", ""])
    for raw_type, count in top_types:
        lines.append(f"- {raw_type}: {count}")
    lines.extend(["", "## Top Generated Classes", ""])
    for row in top_classes:
        lines.append(f"- {row['class_name']}: {row['methods_generated']}/{row['methods_total']} ({row['coverage_pct']}%)")
    lines.append("")
    write(report_path, "\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Generate minimal LeanCLR Godot bindings.")
    parser.add_argument("--api", default="extension_api.json")
    parser.add_argument("--managed-dir", default="managed/GodotSharpCompat")
    parser.add_argument("--src-dir", default="src")
    parser.add_argument("--report", default="tools/binding_generator/unsupported_api_report.json")
    parser.add_argument("--summary-report", default="tools/binding_generator/binding_statistics_report.md")
    args = parser.parse_args()

    with open(args.api, "r", encoding="utf-8") as file:
        api = json.load(file)
    classes, class_order, global_enums, methods, report = build_model(api)
    generate_managed(classes, class_order, global_enums, api.get("builtin_classes", []), methods, Path(args.managed_dir))
    generate_native(classes, methods, Path(args.src_dir))
    generate_report(report, Path(args.report))
    generate_summary_report(report, Path(args.summary_report))


if __name__ == "__main__":
    main()
