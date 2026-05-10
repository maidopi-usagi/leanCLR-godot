# LeanCLR Godot

浅尝一下 LeanCLR 跑 Godot 4 脚本。

原版Godot加载GDExtension，C# 代码交给 LeanCLR 解释执行。现在 demo 里可以把 `.cs` 直接挂到节点上，也可以在游戏窗口里的 CodeEdit 改 C#，点运行后编译一个新 assembly，然后不重启切过去。

已完成：

- Godot API 绑定尽量全量生成，热更代码后面会直接用
- C# 脚本资源能在编辑器里加载、保存、挂节点
- 运行时热重载保留字段状态，接近 Python/Lua 那种 reload 手感
- demo 是一个简单 Flappy Bird，用来测输入、Process、状态迁移和重载

先拉子模块：

```bash
git submodule update --init --recursive
```

编 native 扩展：

```bash
cmake -S . -B build-master
cmake --build build-master --config Debug --target leanclr_godot
```

编 demo 的 C#：

```bash
dotnet msbuild project/Game.csproj /p:Configuration=Debug
```

运行项目:

```bash
/Applications/Godot.app/Contents/MacOS/Godot --path project
```

几个常看的文件：

`src/` :  GDExtension 和 bridge。

`managed/GodotSharpCompat/` : 给 C# 用的 Godot API 外观。

`project/runtime_hot_reload_demo.tscn` : 现在的主 demo。

`project/scripts/HotReloadSmoke.cs` :  Flappy 的 C# 脚本。

`project/scripts/RuntimeCSharpEditor.gd` : 游戏里的 C# 编辑器窗口。

`project/leanclr/live_reload.txt` : 热重载 marker。写 `Game` 就回到默认 `Game.dll`，写别的 assembly 名就切到那个 dll。

