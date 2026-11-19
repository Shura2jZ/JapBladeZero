using CUE4Parse.Compression;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Assets.Exports.Engine;
using System.Reflection;

// Reads and writes the Japanese durations of DT_WwiseVoiceDuration.
//
//   dotnet run -- --dump                       list a few rows
//   dotnet run -- --write durations.tsv        write Duration_Japanese and save
//   dotnet run -- --out <dir>                  where the patched package is written
//
// The written file is a TSV: eventName <TAB> duration in seconds.

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

const string tablePath = "ProjectPBZ/Content/PBZContent/DataTable/Audio/DT_WwiseVoiceDuration.uasset";
var key = provider.Files.Keys.First(k => k.EndsWith(tablePath, StringComparison.OrdinalIgnoreCase));

string writeFile = null, outDir = null;
bool dump = false;
for (int i = 0; i < args.Length; i++)
{
    if (args[i] == "--write") writeFile = args[++i];
    if (args[i] == "--out") outDir = args[++i];
    if (args[i] == "--dump") dump = true;
}

var pk = provider.LoadPackage(provider.Files[key]) as IoPackage;
if (pk is null) { Console.WriteLine("not an IoPackage"); return; }
var table = pk.ExportsLazy.Select(e => e.Value).OfType<UDataTable>().FirstOrDefault();
if (table is null) { Console.WriteLine("no UDataTable export"); return; }
Console.WriteLine($"key={key} rows={table.RowMap.Count} rowStruct={table.RowStructName}");

if (dump)
{
    int n = 0;
    foreach (var kv in table.RowMap)
    {
        Console.WriteLine($"row {kv.Key}");
        DumpRow(kv.Value);
        if (++n >= 3) break;
    }
    return;
}

if (writeFile is null) return;

var wanted = new Dictionary<string, float>();
foreach (var line in File.ReadAllLines(writeFile))
{
    var p = line.Split('\t');
    if (p.Length >= 2 && float.TryParse(p[1], out var d)) wanted[p[0]] = d;
}
Console.WriteLine($"{wanted.Count} durations to write");

int written = 0, missing = 0;
foreach (var kv in table.RowMap)
{
    if (!wanted.TryGetValue(kv.Key.ToString(), out var dur)) { missing++; continue; }
    if (SetFloat(kv.Value, "Duration_Japanese", dur)) written++;
    else Console.WriteLine($"! {kv.Key}: cannot set the duration");
}
Console.WriteLine($"written={written} rows without a duration={missing}");

if (outDir == null) return;
Directory.CreateDirectory(outDir);
if (!provider.TrySavePackage(key, out IReadOnlyDictionary<string, byte[]> files))
{
    Console.WriteLine("cannot save the package");
    return;
}
foreach (var kv in files)
{
    var path = Path.Combine(outDir, Path.GetFileName(kv.Key));
    File.WriteAllBytes(path, kv.Value);
    Console.WriteLine($"  {Path.GetFileName(path)} {kv.Value.Length} bytes");
}

// reload and check
var saved = Path.Combine(outDir, "DT_WwiseVoiceDuration.uasset");
Console.WriteLine("verification:");
var check = OpenFile(saved);
foreach (var kv in check.RowMap.Take(3))
{
    Console.WriteLine($"  row {kv.Key}: Duration_Japanese = {GetFloat(kv.Value, "Duration_Japanese")}");
}

UDataTable OpenFile(string path)
{
    var p = new DefaultFileProvider(Path.GetDirectoryName(path)!, SearchOption.TopDirectoryOnly,
        new VersionContainer(EGame.GAME_PhantomBladeZero));
    p.MappingsContainer = new FileUsmapTypeMappingsProvider(cfg["usmap"]);
    p.Initialize();
    p.SubmitKey(new CUE4Parse.UE4.Objects.Core.Misc.FGuid(), new FAesKey(cfg["aes"]));
    p.PostMount();
    var k = p.Files.Keys.First(x => x.EndsWith("DT_WwiseVoiceDuration.uasset", StringComparison.OrdinalIgnoreCase));
    var pk2 = p.LoadPackage(p.Files[k]) as IoPackage;
    return pk2!.ExportsLazy.Select(e => e.Value).OfType<UDataTable>().First();
}

void DumpRow(object row)
{
    foreach (var tag in TagsOf(row))
    {
        var val = tag.GetType().GetField("Tag")?.GetValue(tag);
        object v = null;
        if (val != null)
        {
            var vf = val.GetType().GetField("Value");
            if (vf != null) v = vf.GetValue(val);
            else v = val.ToString();
        }
        Console.WriteLine($"   {NameOf(tag)} = {v} ({val?.GetType().Name})");
    }
}

float? GetFloat(object row, string name)
{
    foreach (var tag in TagsOf(row))
    {
        if (NameOf(tag) != name) continue;
        if (tag.GetType().GetField("Tag")?.GetValue(tag) is { } val)
        {
            var vf = val.GetType().GetField("Value");
            if (vf != null && vf.GetValue(val) is float fv) return fv;
            var pf = val.GetType().GetProperty("Value");
            if (pf != null && pf.GetValue(val) is float fv2) return fv2;
        }
    }
    return null;
}

IEnumerable<object> TagsOf(object row)
{
    var props = row?.GetType().GetProperty("Properties")?.GetValue(row) as System.Collections.IEnumerable;
    if (props is null) yield break;
    foreach (var p in props) if (p is not null) yield return p;
}

string NameOf(object tag)
{
    var f = tag.GetType().GetField("Name");
    var v = f?.GetValue(tag);
    return v?.ToString() ?? "";
}

bool SetFloat(object row, string name, float value)
{
    foreach (var tag in TagsOf(row))
    {
        if (NameOf(tag) != name) continue;
        var val = tag.GetType().GetField("Tag")?.GetValue(tag);
        if (val is null) continue;
        var vf = val.GetType().GetField("Value");
        if (vf != null && vf.FieldType == typeof(float)) { vf.SetValue(val, value); return true; }
        var pf = val.GetType().GetProperty("Value");
        if (pf != null && pf.PropertyType == typeof(float) && pf.CanWrite) { pf.SetValue(val, value); return true; }
    }
    return false;
}
