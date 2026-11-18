using System.Reflection;

var asm = typeof(CUE4Parse.FileProvider.DefaultFileProvider).Assembly;

// what can write an IoStore container?
foreach (var t in asm.GetTypes().Where(t => t.Name.Contains("IoStore") || t.Name.Contains("Container") || t.Name.Contains("Writer") || t.Name.Contains("Pak")))
{
    var methods = t.GetMethods(BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
        .Where(m => m.Name.Contains("Write") || m.Name.Contains("Save") || m.Name.Contains("Pack") || m.Name.Contains("Create") || m.Name.Contains("Serialize"))
        .ToList();
    if (methods.Count == 0) continue;
    Console.WriteLine($"=== {t.FullName}");
    foreach (var m in methods)
        Console.WriteLine($"  M {(m.IsStatic ? "static " : "")}{m.Name}({string.Join(", ", m.GetParameters().Select(x => x.ParameterType.Name + " " + x.Name))}) -> {m.ReturnType.Name}");
    foreach (var c in t.GetConstructors(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
        Console.WriteLine($"  C ({string.Join(", ", c.GetParameters().Select(x => x.ParameterType.Name + " " + x.Name))})");
}
