using CUE4Parse.Compression;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Assets.Exports.Wwise;
using System.Reflection;

// Extracts cooked packages out of the game's IoStore containers.
//
//   dotnet run -- --events <file>      one event name per line -> build/raw_all
//   dotnet run -- --lib VO_CN          extract a Wwise asset library -> build/libs
//   dotnet run -- --out <dir>          output directory
//
// Each package is written as <name>.uasset plus, when the package has one, <name>.ubulk.
// The tool also reports the packaging strategy of the media of every AkAudioEvent:
//   PrimaryFile / SecondaryFile : the media is bulk data inside the package
//   External                   : the media lives in a Wwise asset library (VO_CN)
//   Inline                     : the media is inline in the .uasset
// which is what decides where a replacement has to be written.

static string FindConfig()
{
    var dir = AppContext.BaseDirectory;
    for (int i = 0; i < 8 && dir != null; i++)
    {
        var c = Path.Combine(dir, "pbz_paths.txt");
        if (File.Exists(c)) return c;
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
provider.MappingsContainer = new FileUsmapTypeMappingsProvider(cfg["usmap"]);
provider.Initialize();
provider.SubmitKey(new CUE4Parse.UE4.Objects.Core.Misc.FGuid(), new FAesKey(cfg["aes"]));
provider.PostMount();

string outDir = "build/raw_all";
string eventsFile = null;
string lib = null;
for (int i = 0; i < args.Length; i++)
{
    switch (args[i])
    {
        case "--events": eventsFile = args[++i]; break;
        case "--out": outDir = args[++i]; break;
        case "--lib": lib = args[++i]; break;
    }
}
Directory.CreateDirectory(outDir);

int ok = 0, fail = 0;

void SavePackage(string key, string name)
{
    if (!provider.TrySavePackage(key, out IReadOnlyDictionary<string, byte[]> data))
    {
        Console.WriteLine($"  ! cannot save {key}");
        fail++;
        return;
    }
    foreach (var kv in data)
    {
        var path = Path.Combine(outDir, name + Path.GetExtension(kv.Key));
        File.WriteAllBytes(path, kv.Value);
        Console.WriteLine($"  {Path.GetFileName(path),-70} {kv.Value.Length,10}");
    }
    ok++;
}

if (lib != null)
{
    var key = provider.Files.Keys.First(k => Path.GetFileNameWithoutExtension(k).Equals(lib, StringComparison.OrdinalIgnoreCase)
                                           && k.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase));
    Console.WriteLine($"library {key}");
    SavePackage(key, lib);
    return;
}

var events = File.ReadAllLines(eventsFile).Select(l => l.Trim()).Where(l => l.Length > 0).ToList();
Console.WriteLine($"{events.Count} events");
foreach (var ev in events)
{
    var key = provider.Files.Keys.FirstOrDefault(k => k.EndsWith("/" + ev + ".uasset", StringComparison.OrdinalIgnoreCase));
    if (key is null) { Console.WriteLine($"  ! {ev}: not found"); fail++; continue; }
    if (!provider.TrySavePackage(key, out IReadOnlyDictionary<string, byte[]> data))
    {
        Console.WriteLine($"  ! {ev}: cannot save");
        fail++;
        continue;
    }
    var names = new List<string>();
    foreach (var kv in data)
    {
        var path = Path.Combine(outDir, ev + Path.GetExtension(kv.Key));
        File.WriteAllBytes(path, kv.Value);
        names.Add(Path.GetFileName(path));
    }
    ok++;
    if (!names.Any(n => n.EndsWith(".ubulk"))) Console.WriteLine($"  {ev}: no .ubulk -> {names.Count} file(s): {string.Join(",", names)}");
}
Console.WriteLine($"extracted {ok}, failed {fail}");
