using System;

namespace Godot
{
    [AttributeUsage(AttributeTargets.Property)]
    public sealed class ExportAttribute : Attribute
    {
        public readonly PropertyHint Hint;
        public readonly string HintString;
        public readonly PropertyUsageFlags Usage;

        public ExportAttribute()
            : this(PropertyHint.None, string.Empty, PropertyUsageFlags.PropertyUsageDefault)
        {
        }

        public ExportAttribute(PropertyHint hint)
            : this(hint, string.Empty, PropertyUsageFlags.PropertyUsageDefault)
        {
        }

        public ExportAttribute(PropertyHint hint, string hintString)
            : this(hint, hintString, PropertyUsageFlags.PropertyUsageDefault)
        {
        }

        public ExportAttribute(PropertyHint hint, string hintString, PropertyUsageFlags usage)
        {
            Hint = hint;
            HintString = hintString ?? string.Empty;
            Usage = usage;
        }
    }
}
