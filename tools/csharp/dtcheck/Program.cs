using CUE4Parse.Compression;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Assets.Exports.Engine;

// Reads the voice duration table the way the engine does, from the mounted
// containers of the game, and compares it with the expected Japanese durations.
//
//   dotnet run -- [--jp data/jp_media_durations.json] [--chinese data/durations.json]
//
// The game has no Japanese voice bank (only Chinese and English), so the
// Japanese audio is installed in the Chinese one: the column the engine reads
// while playing it is Duration_Chinese, and it must carry the Japanese
// duration of the media that is actually played.

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
provider.MappingsContainer = new FileUsmapTypeMappingsProvider(cfg["usmap"]);
provider.Initialize();
provider.SubmitKey(new CUE4Parse.UE4.Objects.Core.Misc.FGuid(), new FAesKey(cfg["aes"]));
provider.PostMount();

const string tablePath = "ProjectPBZ/Content/PBZContent/DataTable/Audio/DT_WwiseVoiceDuration.uasset";
var key = provider.Files.Keys.First(k => k.EndsWith(tablePath, StringComparison.OrdinalIgnoreCase));
var pkg = provider.LoadPackage(provider.Files[key]) as IoPackage;
var table = pkg!.ExportsLazy.Select(e => e.Value).OfType<UDataTable>().FirstOrDefault();
if (table is null) { Console.WriteLine("no UDataTable export"); return 1; }
Console.WriteLine($"rows={table.RowMap.Count} rowStruct={table.RowStructName}");

string jpFile = "data/jp_media_durations.json", cnFile = "data/durations.json";
for (int i = 0; i < args.Length; i++)
{
    if (args[i] == "--jp") jpFile = args[++i];
    if (args[i] == "--chinese") cnFile = args[++i];
}
var jp = LoadDurations(jpFile);
var cn = LoadDurations(cnFile);

int patched = 0, untouched = 0, missing = 0, other = 0;
double worst = 0;
var samples = new List<string>();
foreach (var kv in table.RowMap)
{
    var ev = kv.Key.ToString();
    if (!jp.TryGetValue(ev, out var expected)) { missing++; continue; }
    var got = GetFloat(kv.Value, "Duration_Chinese");
    if (got is null) { missing++; continue; }
    if (Math.Abs(got.Value - expected) < 1e-4) { patched++; continue; }
    var original = cn.TryGetValue(ev, out var c) ? c : 0;
    if (Math.Abs(got.Value - original) < 1e-4) { untouched++; continue; }
    other++;
    var delta = Math.Abs(got.Value - expected);
    if (delta > worst) worst = delta;
    if (samples.Count < 8)
        samples.Add($"  {ev}: got {got.Value} expected {expected} (chinese was {original})");
}
Console.WriteLine($"rows with a Japanese duration : {jp.Count}");
Console.WriteLine($"  Chinese column = Japanese duration : {patched}");
Console.WriteLine($"  Chinese column = original Chinese : {untouched}");
Console.WriteLine($"  other                            : {other}");
Console.WriteLine($"  no duration at all                : {missing}");
Console.WriteLine($"worst difference on the others      : {worst:F6} s");
foreach (var s in samples) Console.WriteLine(s);
return 0;

float? GetFloat(object row, string name)
{
    var props = row?.GetType().GetProperty("Properties")?.GetValue(row) as System.Collections.IEnumerable;
    if (props is null) return null;
    foreach (var p in props)
    {
        if (p is null) continue;
        // the property carries its name; the value is inside its tag
        var pname = p.GetType().GetField("Name")?.GetValue(p)?.ToString();
        if (pname != name) continue;
        var tag = p.GetType().GetField("Tag")?.GetValue(p);
        if (tag is null) continue;
        var t = tag.GetType();
        var vf = t.GetField("Value");
        if (vf != null && vf.GetValue(tag) is float fv) return fv;
        var pf = t.GetProperty("Value");
        if (pf != null && pf.GetValue(tag) is float fv2) return fv2;
    }
    return null;
}

// the durations are either a JSON object (event -> duration) or a TSV
static Dictionary<string, float> LoadDurations(string path)
{
    var result = new Dictionary<string, float>();
    var text = File.ReadAllText(path).Trim();
    if (text.StartsWith('{'))
    {
        using var doc = System.Text.Json.JsonDocument.Parse(text);
        foreach (var p in doc.RootElement.EnumerateObject())
            if (p.Value.ValueKind == System.Text.Json.JsonValueKind.Number)
                result[p.Name] = p.Value.GetSingle();
        return result;
    }
    foreach (var line in text.Split('\n').Skip(text.StartsWith("event") ? 1 : 0))
    {
        var p = line.Split('\t');
        if (p.Length >= 2 && float.TryParse(p[1], out var d)) result[p[0]] = d;
    }
    return result;
}
