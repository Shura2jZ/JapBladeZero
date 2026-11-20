using CUE4Parse.Compression;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.Encryption.Aes;

// Extracts the raw bytes of a package of the game, as the engine loads them, and
// writes them to a file. Used to check that a locally patched .uasset is byte
// for byte the chunk the engine resolves.
//
//   dotnet run -- --path <game path> --out <file>

static string FindConfig()
{
    var dir = AppContext.BaseDirectory;
    for (int i = 0; i < 8 && dir != null; i++)
    {
        var p = Path.Combine(dir, "pbz_paths.txt");
        if (File.Exists(p)) return p;
        dir = Path.GetDirectoryName(dir.TrimEnd(Path.DirectorySeparatorChar));
    }
    throw new FileNotFoundException("pbz_paths.txt not found");
}
var cfg = new Dictionary<string, string>();
foreach (var line in File.ReadAllLines(FindConfig()))
{
    if (string.IsNullOrWhiteSpace(line) || !line.Contains('=')) continue;
    var i = line.IndexOf('=');
    cfg[line[..i].Trim()] = line[(i + 1)..].Trim();
}

OodleHelper.Initialize(cfg["oodle"]);
var provider = new DefaultFileProvider(cfg["paks"], System.IO.SearchOption.TopDirectoryOnly,
    new VersionContainer(EGame.GAME_PhantomBladeZero));
provider.MappingsContainer = new CUE4Parse.MappingsProvider.Usmap.FileUsmapTypeMappingsProvider(cfg["usmap"]);
provider.Initialize();
provider.SubmitKey(new CUE4Parse.UE4.Objects.Core.Misc.FGuid(), new FAesKey(cfg["aes"]));
provider.PostMount();

string path = null, outFile = null;
for (int i = 0; i < args.Length; i++)
{
    if (args[i] == "--path") path = args[++i];
    if (args[i] == "--out") outFile = args[++i];
}
if (path == null || outFile == null) { Console.WriteLine("usage: --path <game path> --out <file>"); return 1; }

var key = provider.Files.Keys.FirstOrDefault(k => k.EndsWith(path, StringComparison.OrdinalIgnoreCase));
if (key is null) { Console.WriteLine("not found: " + path); return 1; }
Console.WriteLine("key=" + key);

if (!provider.TrySavePackage(key, out var files))
{
    Console.WriteLine("cannot save the package");
    return 1;
}
foreach (var kv in files)
{
    var name = Path.GetFileName(kv.Key);
    var dest = outFile.EndsWith(".uasset") && name.EndsWith(".uasset")
        ? outFile
        : Path.Combine(Path.GetDirectoryName(outFile)!, name);
    File.WriteAllBytes(dest, kv.Value);
    Console.WriteLine($"  {name} {kv.Value.Length} bytes -> {dest}");
}
return 0;
