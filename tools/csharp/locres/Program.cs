using CUE4Parse.Compression;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Assets.Exports.Wwise;
using CUE4Parse.UE4.Assets.Objects;
using CUE4Parse.UE4.Wwise;
using CUE4Parse.UE4.Localization;
using CUE4Parse.UE4.Objects.Core.i18N;
using System.Reflection;
using System.Text.Json;

// Dumps the compiled localization resources (.locres) of the game as JSON.
//
//   dotnet run -- --out <dir> [--culture ja]
//
// The .locres files hold the FTextLocalizationResource of a culture (ja,
// en-US, zh-Hans, ...): every dialogue line of the game, in that language.
// If the ja culture holds the dialogue lines, the game already has its own
// Japanese script, and that text is the reference the TTS should read instead
// of a machine translation.

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

string outDir = Path.Combine("E:/PBZ_Build/build", "locres");
string culture = null;
bool metaMode = false;
for (int i = 0; i < args.Length; i++)
{
    if (args[i] == "--out") outDir = args[++i];
    if (args[i] == "--culture") culture = args[++i];
    if (args[i] == "--meta") { metaMode = true; }
}
Directory.CreateDirectory(outDir);

if (metaMode)
{
    foreach (var p in provider.Files.Keys.Where(p => p.StartsWith("ProjectPBZ/Content/Localization/Game/", StringComparison.OrdinalIgnoreCase) && p.EndsWith(".locmeta", StringComparison.OrdinalIgnoreCase)))
    {
        using var reader = provider.CreateReader(p);
        var meta = new FTextLocalizationMetaDataResource(reader);
        Console.WriteLine($"{p}");
        Console.WriteLine($"  native      : {meta.NativeCulture}  ({meta.NativeLocRes})");
        Console.WriteLine($"  compiles    : {string.Join(", ", meta.CompiledCultures ?? new string[0])}");
    }
    return;
}

const string prefix = "ProjectPBZ/Content/Localization/Game/";
var wanted = provider.Files.Keys
    .Where(p => p.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) && p.EndsWith(".locres", StringComparison.OrdinalIgnoreCase))
    .OrderBy(p => p)
    .ToList();

Console.WriteLine($"localization resources of the game: {wanted.Count}");
foreach (var p in wanted)
{
    var rel = p.Substring(prefix.Length).Replace('/', '_');
    if (culture != null && !rel.StartsWith(culture, StringComparison.OrdinalIgnoreCase)) continue;
    try
    {
        using var reader = provider.CreateReader(p);
        var res = new FTextLocalizationResource(reader);
        var dict = new Dictionary<string, string>();
        foreach (var ns in res.Entries)
            foreach (var kv in ns.Value)
                dict[ns.Key.Str + ":" + kv.Key.Str] = kv.Value.LocalizedString;
        var dest = Path.Combine(outDir, rel.Replace(".locres", ".json"));
        File.WriteAllText(dest, JsonSerializer.Serialize(dict, new JsonSerializerOptions { WriteIndented = false }));
        var dlg = dict.Keys.Count(k => k.Contains(":Dlg_"));
        Console.WriteLine($"  {rel}: {dict.Count} entries ({dlg} Dlg_) -> {dest}");
        foreach (var kv in dict.Where(k => k.Key.Contains(":Dlg_")).Take(4))
            Console.WriteLine($"      {kv.Key} -> {kv.Value}");
    }
    catch (Exception e)
    {
        Console.WriteLine($"  {p}: {e.GetType().Name}: {e.Message}");
    }
}
