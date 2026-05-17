# LeanCLR Web Compiler

Browser-side Roslyn compiler sidecar for the Godot Web demo.

Build and copy into the Godot project export payload:

```bash
dotnet publish tools/LeanCLRWebCompiler/LeanCLRWebCompiler.csproj -c Release -o project/web_compiler
```

The Godot page loads `web_compiler/_framework/blazor.webassembly.js` and `web/leanclr_web_compiler_boot.js`. The boot script exposes:

```js
window.LeanCLR.compileCSharp(assemblyName, source)
```

It returns `{ state, assemblyName, dllBase64, message }`. Godot writes the DLL bytes to `user://leanclr` and asks `LeanCLRHotReloadHost` to reload that assembly.
