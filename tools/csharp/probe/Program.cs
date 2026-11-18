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

// --- configuration comes from pbz_paths.txt (kept out of the source) ---
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

Console.WriteLine($"paks=[{cfg["paks"]}] exists={Directory.Exists(cfg["paks"])} files={provider.Files.Count}");
foreach (var k in provider.Files.Keys.Where(k => k.Contains("Hun_10_1")).Take(10)) Console.WriteLine("  MATCH " + k);
Console.WriteLine("--- filtering ---");
Console.WriteLine("args=[" + string.Join(",", args) + "]");
string ev = "Vo_Plot_2D_Animation1_Hun_10_1";
var key = provider.Files.Keys.First(k => k.EndsWith("/" + ev + ".uasset", StringComparison.OrdinalIgnoreCase)
                                       && k.Contains("/Plot/2D/"));
Console.WriteLine("key=" + key);
var pk = provider.LoadPackage(provider.Files[key]) as IoPackage;
var evt = pk.ExportsLazy[0].Value as UAkAudioEvent;

void Dump(string label, object o)
{
    if (o is FByteBulkData bd)
    {
        var h = bd.Header;
        long len = 0;
        try { len = bd.GetDataSize(); } catch { }
        Console.WriteLine($"{label}: flags={h.BulkDataFlags} elem={h.ElementCount} size={h.SizeOnDisk} off={h.OffsetInFile} len={len}");
        return;
    }
    Console.WriteLine($"{label}: {o?.GetType().Name ?? "null"}");
}

// every FByteBulkData reachable from the export, found via the export's own properties
Console.WriteLine($"== export {evt.GetType().Name} direct properties ==");
foreach (var p in evt.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance))
{
    object v = null;
    try { v = p.GetValue(evt); } catch { continue; }
    if (v is FByteBulkData f) Dump("  " + p.Name, f);
}

var langMap = evt.EventCookedData.GetType().GetField("EventLanguageMap").GetValue(evt.EventCookedData) as System.Collections.IDictionary;
foreach (System.Collections.DictionaryEntry kv in langMap)
{
    var langName = kv.Key.GetType().GetField("LanguageName").GetValue(kv.Key)?.ToString();
    var cooked = kv.Value;
    var mediaArr = cooked.GetType().GetField("Media").GetValue(cooked) as Array;
    Console.WriteLine($"== {langName}: {mediaArr?.Length} media ==");
    for (int i = 0; i < (mediaArr?.Length ?? 0); i++)
    {
        var m = mediaArr.GetValue(i);
        var pf = m.GetType().GetField("PackagedFile").GetValue(m);
        var reader = pf.GetType().GetField("BulkData").GetValue(pf) as WwiseReader;
        var wem = reader.WemFile;
        var bd = wem.GetType().GetField("BulkData").GetValue(wem);
        Dump($"  [{i}] WemFile.BulkData", bd);
    }
}

// brute-force scan of every field of the export object graph, 3 levels deep, looking
// for FByteBulkData / FStructFallback holding them
Console.WriteLine("== deep scan ==");
var seen = new HashSet<object>();
int found = 0;
void Deep(object o, string path, int depth)
{
    if (o is null || depth > 3 || o is string || o is byte[]) return;
    if (o is FByteBulkData b) { Dump("  deep " + path, b); found++; return; }
    var t = o.GetType();
    if (t.IsPrimitive || t.IsEnum) return;
    if (!seen.Add(o)) return;
    foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.Instance))
    {
        object v = null;
        try { v = f.GetValue(o); } catch { continue; }
        if (v is null || v is string || v is byte[]) continue;
        if (v is System.Collections.IEnumerable en and not string)
        {
            int k = 0;
            foreach (var it in en) Deep(it, $"{path}.{f.Name}[{k++}]", depth + 1);
        }
        else Deep(v, $"{path}.{f.Name}", depth + 1);
    }
}
Deep(evt, "evt", 0);
Console.WriteLine($"deep found {found} bulk data");
