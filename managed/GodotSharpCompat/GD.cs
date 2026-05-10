using System.Runtime.CompilerServices;

namespace Godot
{
    public static class GD
    {
        public static void Print(string message)
        {
            PrintInternal(message);
        }

        [MethodImpl(MethodImplOptions.InternalCall)]
        private static extern void PrintInternal(string message);
    }
}
