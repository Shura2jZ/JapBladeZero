using System.Reflection;
var asm = typeof(CUE4Parse.FileProvider.DefaultFileProvider).Assembly;
foreach (var t in asm.GetTypes().Where(t => t.Name.Contains("DataTable")))
{
    Console.WriteLine("== " + t.FullName);
    foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.DeclaredOnly))
        Console.WriteLine($"   F {f.FieldType.Name} {f.Name}");
    foreach (var p in t.GetProperties(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.DeclaredOnly))
        Console.WriteLine($"   P {p.PropertyType.Name} {p.Name} get={p.CanRead} set={p.CanWrite}");
}
