using System;
using System.Collections.Generic;

namespace Godot
{
    internal static class CallableDelegateRegistry
    {
        private static readonly Dictionary<long, Func<Variant[], Variant>> Delegates = new Dictionary<long, Func<Variant[], Variant>>();
        private static long nextId = 1;

        internal static long Register(Func<Variant[], Variant> function)
        {
            long id = nextId++;
            Delegates[id] = function;
            return id;
        }

        internal static void Unregister(long delegateId)
        {
            Delegates.Remove(delegateId);
        }

        public static Variant Invoke(long delegateId, Variant[] arguments)
        {
            Func<Variant[], Variant> function;
            if (!Delegates.TryGetValue(delegateId, out function))
            {
                return new Variant();
            }
            return function(arguments ?? new Variant[0]);
        }

        internal static T ConvertArgument<T>(Variant[] arguments, int index)
        {
            Variant value = arguments[index];
            Type type = typeof(T);
            if (type == typeof(Variant))
            {
                return (T)(object)value;
            }
            if (type == typeof(string))
            {
                return (T)(object)value.ToString();
            }
            if (type == typeof(int))
            {
                return (T)(object)(int)value.AsInt64();
            }
            if (type == typeof(long))
            {
                return (T)(object)value.AsInt64();
            }
            if (type == typeof(float))
            {
                return (T)(object)(float)value.AsDouble();
            }
            if (type == typeof(double))
            {
                return (T)(object)value.AsDouble();
            }
            if (type == typeof(bool))
            {
                return (T)(object)value.AsBool();
            }
            if (type == typeof(Vector2))
            {
                return (T)(object)value.AsVector2();
            }
            if (type == typeof(Vector3))
            {
                return (T)(object)value.AsVector3();
            }
            if (type == typeof(StringName))
            {
                return (T)(object)value.AsStringName();
            }
            if (type == typeof(NodePath))
            {
                return (T)(object)value.AsNodePath();
            }
            if (type == typeof(RID))
            {
                return (T)(object)value.AsRID();
            }
            if (type == typeof(Color))
            {
                return (T)(object)value.AsColor();
            }
            if (type == typeof(Quaternion))
            {
                return (T)(object)value.AsQuaternion();
            }
            if (type == typeof(Basis))
            {
                return (T)(object)value.AsBasis();
            }
            if (type == typeof(Transform3D))
            {
                return (T)(object)value.AsTransform3D();
            }
            if (type == typeof(Node))
            {
                return (T)(object)value.AsObject<Node>();
            }
            if (type == typeof(Node2D))
            {
                return (T)(object)value.AsObject<Node2D>();
            }
            if (type == typeof(GodotObject))
            {
                return (T)(object)value.AsObject<GodotObject>();
            }
            return default(T);
        }
    }
}
