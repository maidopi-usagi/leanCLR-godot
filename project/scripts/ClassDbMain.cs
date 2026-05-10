using Godot;

namespace Game;

public partial class ClassDbMain : Node
{
    public override void _Ready()
    {
        GD.Print("LeanCLR demo: ClassDB host owner name = " + Name);
    }
}
