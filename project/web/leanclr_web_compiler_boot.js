(function () {
  if (window.LeanCLR && window.LeanCLR.compileCSharp) {
    return;
  }

  window.LeanCLR = window.LeanCLR || {};
  window.LeanCLR.compileCSharp = async function (assemblyName, source) {
    if (window.LeanCLRCompilerReady) {
      await window.LeanCLRCompilerReady;
    }

    if (!window.DotNet || !window.DotNet.invokeMethodAsync) {
      return {
        state: 'error',
        message: 'Blazor WebAssembly runtime is not ready. Build tools/LeanCLRWebCompiler and copy its publish output to project/web_compiler.'
      };
    }

    return await window.DotNet.invokeMethodAsync('LeanCLRWebCompiler', 'CompileCSharp', assemblyName, source);
  };
})();
