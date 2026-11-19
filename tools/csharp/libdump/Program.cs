using CUE4Parse.Compression;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Assets.Objects;
using System.Reflection;

// Dumps a Wwise asset library (UWwiseAssetLibrary): the chunks it holds and their sizes.
//
//   dotnet run -- --lib VO_CN
//   dotnet run -- --lib VO_CN --find Vo_Plot_DDSD_GM_GM_25

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

string libName = args.FirstOrDefault(a => !a.StartsWith("--")) ?? "VO_CN";
string find = args.SkipWhile(a => a != "--find").Skip(1).FirstOrDefault() ?? "";
int limit = int.TryParse(args.SkipWhile(a => a != "--limit").Skip(1).FirstOrDefault(), out var l) ? l : 40;

var key = provider.Files.Keys.First(k => Path.GetFileNameWithoutExtension(k).Equals(libName, StringComparison.OrdinalIgnoreCase)
                                       && k.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase));
Console.WriteLine($"library {key}  size={provider.Files[key].Size}");
var pk = provider.LoadPackage(provider.Files[key]) as IoPackage;
if (pk is null) { Console.WriteLine("not an IoPackage"); return; }

int total = 0, printed = 0;
var seen = new HashSet<object>();

void Walk(object o, string path, int depth)
{
    if (o is null || depth > 4 || o is string || o is byte[]) return;
    var t = o.GetType();
    if (t.IsPrimitive || t.IsEnum) return;
    if (!seen.Add(o)) return;
    foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.Instance))
    {
        object v = null;
        try { v = f.GetValue(o); } catch { continue; }
        if (v is null) { if (depth <= 2) Console.WriteLine($"    {path}.{f.Name} = null ({t.Name})"); continue; }
        if (v is System.Collections.IDictionary dict)
        {
            Console.WriteLine($"  {path}.{f.Name}: dict[{dict.Count}]");
            foreach (System.Collections.DictionaryEntry kv in dict)
            {
                total++;
                string name = kv.Key?.ToString() ?? "";
                long size = 0;
                string extra = "";
                try
                {
                    var bo = kv.Value;
                    var bt = bo?.GetType();
                    var bd = (bt?.GetField("BulkData")?.GetValue(bo) ?? bt?.GetField("Data")?.GetValue(bo)) as FByteBulkData;
                    if (bd != null)
                    {
                        size = bd.Header.SizeOnDisk;
                        extra = $"off={bd.Header.OffsetInFile} flags={bd.Header.BulkDataFlags}";
                    }
                    else
                    {
                        var pinch = bt?.GetProperty("ChunkSize")?.GetValue(bo);
                        if (pinch is long pl) size = pl;
                    }
                }
                catch { }
                if (find.Length > 0 && !name.Contains(find, StringComparison.OrdinalIgnoreCase)) continue;
                printed++;
                Console.WriteLine($"    {name}  size={size} {extra}");
                if (printed > limit) { Console.WriteLine("    ..."); break; }
            }
            continue;
        }
        if (v is System.Collections.IEnumerable en and not string)
        {
            int cnt = 0;
            foreach (var it in en)
            {
                cnt++;
                if (cnt <= 2) Walk(it, $"{path}.{f.Name}[{cnt - 1}]", depth + 1);
            }
            Console.WriteLine($"    {path}.{f.Name}[] : {cnt} items");
            continue;
        }
        if (v.GetType().Name.StartsWith("F") || v.GetType().Name.StartsWith("UAk") || v.GetType().Name.StartsWith("UWwise"))
        {
            Walk(v, $"{path}.{f.Name}", depth + 1);
            Console.WriteLine($"    {path}.{f.Name} : {v.GetType().Name}");
        }
    }
}

if (args.Contains("--paths"))
{
    var cd = pk.ExportsLazy[0].Value.GetType().GetField("CookedData")!.GetValue(pk.ExportsLazy[0].Value)!;
    var pf = cd.GetType().GetField("PackagedFiles")!.GetValue(cd)!;
    var arr = (Array)pf;
    Console.WriteLine($"packaged files: {arr.Length}");
    for (int i = 0; i < arr.Length; i++)
    {
        var o = arr.GetValue(i)!;
        var pname = o.GetType().GetField("PathName")!.GetValue(o);
        var mname = o.GetType().GetField("ModularGameplayName")!.GetValue(o);
        var hash = o.GetType().GetField("Hash")?.GetValue(o);
        var strat = o.GetType().GetField("PackagingStrategy")?.GetValue(o);
        var bulk = o.GetType().GetField("BulkData")?.GetValue(o);
        long size = 0;
        if (bulk is FByteBulkData bd) size = bd.Header.SizeOnDisk;
        Console.WriteLine($"{i}	{pname}	{mname}	{hash}	{strat}	size={size}");
    }
    return;
}

foreach (var exp in pk.ExportsLazy)
{
    Console.WriteLine($"export {exp.Value?.GetType().FullName}");
    Walk(exp.Value, "exp", 0);
}
Console.WriteLine($"chunks total={total} printed={printed}");
