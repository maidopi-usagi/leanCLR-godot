using System;
using System.Collections.Generic;

namespace Godot
{
    public partial class GodotObject : System.IDisposable
    {
        private static readonly Dictionary<IntPtr, WeakReference> NativeInstanceCache = new Dictionary<IntPtr, WeakReference>();

        internal System.IntPtr NativePtr;
        private int ownedNativeRefCount;

        internal static T CreateFromNative<T>(System.IntPtr nativePtr) where T : GodotObject, new()
        {
            return CreateFromNative<T>(nativePtr, false);
        }

        internal static T CreateFromNative<T>(System.IntPtr nativePtr, bool ownsNativeRef) where T : GodotObject, new()
        {
            if (nativePtr == System.IntPtr.Zero)
            {
                return null;
            }

            WeakReference weakReference;
            if (NativeInstanceCache.TryGetValue(nativePtr, out weakReference))
            {
                T cached = weakReference.Target as T;
                if (cached != null && cached.NativePtr == nativePtr)
                {
                    if (ownsNativeRef)
                    {
                        cached.ownedNativeRefCount++;
                    }
                    return cached;
                }
            }

            T instance = new T();
            instance.NativePtr = nativePtr;
            instance.ownedNativeRefCount = ownsNativeRef ? 1 : 0;
            NativeInstanceCache[nativePtr] = new WeakReference(instance);
            return instance;
        }

        ~GodotObject()
        {
            Dispose(false);
        }

        public void Dispose()
        {
            Dispose(true);
            System.GC.SuppressFinalize(this);
        }

        protected virtual void Dispose(bool disposing)
        {
            if (NativePtr == System.IntPtr.Zero)
            {
                return;
            }

            NativeInstanceCache.Remove(NativePtr);
            while (ownedNativeRefCount > 0)
            {
                NativeCalls.GodotObjectReleaseRefCounted(NativePtr);
                ownedNativeRefCount--;
            }
            NativePtr = System.IntPtr.Zero;
        }
    }
}
