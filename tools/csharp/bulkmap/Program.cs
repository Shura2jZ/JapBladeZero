using CUE4Parse.Compression;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets;
using System.Reflection;

// Dumps the bulk data map of a package: the ordered list of the bulk data blocks, with
// the chunk id (SerialOffset) and the size of each block.
//
//   dotnet run -- --lib VO_CN
//   dotnet run -- --events <file>
//
// The serial offset of a bulk data entry is the chunk id of the block, which is what
// links a block of the .ubulk to the media it holds.

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

void Dump(string key, string label)
{
    var pk = provider.LoadPackage(provider.Files[key]) as IoPackage;
    if (pk is null) { Console.WriteLine($"{label}: not an IoPackage"); return; }
    var field = typeof(IoPackage).GetField("BulkDataMap", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
    var arr = field?.GetValue(pk) as Array;
    Console.WriteLine($"{label}: {arr?.Length ?? 0} bulk data entries");
    if (arr is null) return;
    for (int i = 0; i < arr.Length; i++)
    {
        var e = arr.GetValue(i)!;
        var t = e.GetType();
        ulong serial = Convert.ToUInt64(t.GetField("SerialOffset")!.GetValue(e));
        ulong dup = Convert.ToUInt64(t.GetField("DuplicateSerialOffset")!.GetValue(e));
        uint size = Convert.ToUInt32(t.GetField("SerialSize")!.GetValue(e));
        uint flags = Convert.ToUInt32(t.GetField("Flags")!.GetValue(e));
        Console.WriteLine($"  {i}\tid=0x{serial:X16}\tdup=0x{dup:X16}\tsize={size}\tflags={flags}");
    }
}

string lib = null, eventsFile = null;
for (int i = 0; i < args.Length; i++)
{
    if (args[i] == "--lib") lib = args[++i];
    if (args[i] == "--events") eventsFile = args[++i];
}

if (lib != null)
{
    var key = provider.Files.Keys.First(k => Path.GetFileNameWithoutExtension(k).Equals(lib, StringComparison.OrdinalIgnoreCase)
                                           && k.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase));
    Dump(key, lib);
    return;
}

foreach (var ev in File.ReadAllLines(eventsFile!).Select(l => l.Trim()).Where(l => l.Length > 0))
{
    var key = provider.Files.Keys.FirstOrDefault(k => k.EndsWith("/" + ev + ".uasset", StringComparison.OrdinalIgnoreCase));
    if (key is null) { Console.WriteLine($"! {ev} not found"); continue; }
    Dump(key, ev);
}
