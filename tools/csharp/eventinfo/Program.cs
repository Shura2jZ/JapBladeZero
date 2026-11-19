using CUE4Parse.Compression;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Assets.Exports.Wwise;
using CUE4Parse.UE4.Assets.Objects;
using CUE4Parse.UE4.Wwise;
using System.Reflection;

// Inspects one voice event package: where it lives, whether it has a .ubulk, and
// where each language's media is stored.
//
//   dotnet run -- <event_name> [<event_name> ...]
//   dotnet run -- --list <dir substring>      list the files of a directory


// a readable value for the fields we care about (FName, enums, numbers)
static string Describe(object v)
{
    if (v is null) return "null";
    if (v is string s) return "\"" + s + "\"";
    if (v != null && v.GetType().Name == "FName") return "\"" + v.ToString() + "\"";
    if (v is uint u) return u + " (0x" + u.ToString("X8") + ")";
    if (v is int i) return i.ToString();
    if (v is bool b) return b.ToString();
    if (v.GetType().IsEnum) return v.ToString();
    return v.GetType().Name;
}

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

if (args.Length > 0 && args[0] == "--list")
{
    string sub = args.Length > 1 ? args[1] : "";
    foreach (var k in provider.Files.Keys.Where(k => k.Contains(sub)).OrderBy(k => k).Take(400))
        Console.WriteLine($"{provider.Files[k].Size,10}  {k}");
    return;
}

foreach (var ev in args)
{
    Console.WriteLine($"===================== {ev}");
    var matches = provider.Files.Keys.Where(k => k.EndsWith("/" + ev + ".uasset", StringComparison.OrdinalIgnoreCase)).ToList();
    if (matches.Count == 0) { Console.WriteLine("  not found"); continue; }
    foreach (var key in matches)
    {
        Console.WriteLine($"  key={key}");
        string dir = Path.GetDirectoryName(key)!.Replace('\\', '/');
        var siblings = provider.Files.Keys.Where(k => Path.GetDirectoryName(k)!.Replace('\\', '/') == dir)
            .OrderBy(k => k).ToList();
        Console.WriteLine($"  dir={dir}  files in dir={siblings.Count}");
        foreach (var s in siblings.Take(12))
            Console.WriteLine($"     {provider.Files[s].Size,10}  {Path.GetFileName(s)}");
        if (siblings.Count > 12) Console.WriteLine("     ...");

        var pk = provider.LoadPackage(provider.Files[key]) as IoPackage;
        if (pk is null) { Console.WriteLine("  not an IoPackage"); continue; }
        bool hasBulk = provider.Files.Keys.Any(k => k.Equals(key.Substring(0, key.Length - ".uasset".Length) + ".ubulk", StringComparison.OrdinalIgnoreCase));
        Console.WriteLine($"  has .ubulk sibling: {hasBulk}");
        foreach (var exp in pk.ExportsLazy)
        {
            var o = exp.Value;
            Console.WriteLine($"  export {o?.GetType().Name} ({(o is UAkAudioEvent ? "AkAudioEvent" : "")})");
            if (o is not UAkAudioEvent evt) continue;
            var langMap = evt.EventCookedData.GetType().GetField("EventLanguageMap")!.GetValue(evt.EventCookedData)! as System.Collections.IDictionary;
            foreach (System.Collections.DictionaryEntry kv in langMap)
            {
                var langName = kv.Key.GetType().GetField("LanguageName")!.GetValue(kv.Key)?.ToString();
                var cooked = kv.Value!;
                var mediaArr = cooked.GetType().GetField("Media")!.GetValue(cooked) as Array;
                Console.WriteLine($"    {langName}: {mediaArr?.Length ?? 0} media");
                for (int i = 0; i < (mediaArr?.Length ?? 0); i++)
                {
                    var m = mediaArr!.GetValue(i)!;
                    foreach (var f in m.GetType().GetFields(BindingFlags.Public | BindingFlags.Instance))
                    {
                        object v = null;
                        try { v = f.GetValue(m); } catch { continue; }
                        Console.WriteLine($"      [{i}].{f.Name} = {Describe(v)}");
                    }
                    var pf = m.GetType().GetField("PackagedFile")?.GetValue(m);
                    if (pf is null) { Console.WriteLine($"      [{i}] no PackagedFile"); continue; }
                    foreach (var f in pf.GetType().GetFields(BindingFlags.Public | BindingFlags.Instance))
                    {
                        object v = null;
                        try { v = f.GetValue(pf); } catch { continue; }
                        Console.WriteLine($"        PackagedFile.{f.Name} = {Describe(v)}");
                        if (f.Name.Contains("Wem") || f.Name.Contains("Bulk"))
                        {
                            foreach (var g in v?.GetType().GetFields(BindingFlags.Public | BindingFlags.Instance) ?? Array.Empty<System.Reflection.FieldInfo>())
                            {
                                object w = null;
                                try { w = g.GetValue(v); } catch { continue; }
                                Console.WriteLine($"          .{g.Name} = {Describe(w)}");
                                if (w is FByteBulkData bd2)
                                {
                                    var h = bd2.Header;
                                    long len = 0;
                                    try { len = bd2.GetDataSize(); } catch { }
                                    Console.WriteLine($"            flags={h.BulkDataFlags} elem={h.ElementCount} size={h.SizeOnDisk} off={h.OffsetInFile} len={len}");
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
