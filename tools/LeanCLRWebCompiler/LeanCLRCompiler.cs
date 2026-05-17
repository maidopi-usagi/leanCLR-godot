using System.Collections.Immutable;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.Emit;
using Microsoft.JSInterop;

namespace LeanCLRWebCompiler;

public sealed record CompileResponse(string State, string AssemblyName, string DllBase64, string Message);

public static partial class LeanCLRCompiler
{
    private static readonly string[] ReferencePaths =
    [
        "web_compiler/leanclr/mscorlib.dll",
        "web_compiler/leanclr/System.dll",
        "web_compiler/leanclr/GodotSharpCompat.dll",
    ];

    private static HttpClient? httpClient;
    private static ImmutableArray<MetadataReference>? references;

    public static void Configure(HttpClient client)
    {
        httpClient = client;
    }

    [JSInvokable]
    public static async Task<CompileResponse> CompileCSharp(string assemblyName, string source)
    {
        if (httpClient == null)
        {
            return Error(assemblyName, "Compiler HTTP client is not configured.");
        }

        try
        {
            ImmutableArray<MetadataReference> loadedReferences = await GetReferences();
            SyntaxTree syntaxTree = CSharpSyntaxTree.ParseText(source, new CSharpParseOptions(LanguageVersion.Latest));
            CSharpCompilation compilation = CSharpCompilation.Create(
                assemblyName,
                [syntaxTree],
                loadedReferences,
                new CSharpCompilationOptions(
                    OutputKind.DynamicallyLinkedLibrary,
                    optimizationLevel: OptimizationLevel.Debug,
                    allowUnsafe: false));

            await using MemoryStream dllStream = new();
            EmitResult result = compilation.Emit(dllStream);
            string diagnostics = string.Join("\n", result.Diagnostics
                .Where(diagnostic => diagnostic.Severity is DiagnosticSeverity.Error or DiagnosticSeverity.Warning)
                .Select(static diagnostic => diagnostic.ToString()));

            if (!result.Success)
            {
                return Error(assemblyName, diagnostics == string.Empty ? "Compilation failed." : diagnostics);
            }

            return new CompileResponse("ok", assemblyName, Convert.ToBase64String(dllStream.ToArray()), diagnostics);
        }
        catch (Exception ex)
        {
            return Error(assemblyName, ex.ToString());
        }
    }

    private static async Task<ImmutableArray<MetadataReference>> GetReferences()
    {
        if (references.HasValue)
        {
            return references.Value;
        }

        List<MetadataReference> loadedReferences = [];
        foreach (string path in ReferencePaths)
        {
            byte[] bytes = await httpClient!.GetByteArrayAsync(path);
            loadedReferences.Add(MetadataReference.CreateFromImage(bytes));
        }

        references = [.. loadedReferences];
        return references.Value;
    }

    private static CompileResponse Error(string assemblyName, string message)
    {
        return new CompileResponse("error", assemblyName, string.Empty, message);
    }
}
