using System.Reflection;
using CUE4Parse.Compression;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Assets.Exports.Wwise;
using CUE4Parse.UE4.Assets.Objects;
using CUE4Parse.UE4.IO;
using CUE4Parse.UE4.IO.Objects;
using CUE4Parse.UE4.Wwise;

// Dumps every export of an event package and the imports it references.
//
//   exports <event>

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
var provider = new DefaultFileProvider(cfg["paks"], SearchOption.TopDirectoryOnly,
    new VersionContainer(EGame.GAME_PhantomBladeZero));
provider.MappingsContainer = new FileUsmapTypeMappingsProvider(cfg["usmap"]);
provider.Initialize();
provider.SubmitKey(default, new FAesKey(cfg["aes"]));
provider.PostMount();

var evName = args[^1];
var key = provider.Files.Keys.First(k => k.EndsWith("/" + evName + ".uasset", StringComparison.OrdinalIgnoreCase));
Console.WriteLine($"key={key}");
var pkg = provider.LoadPackage(provider.Files[key]) as IoPackage ?? throw new Exception("not an IoPackage");

Console.WriteLine($"exports={pkg.ExportMapLength} imports={pkg.ImportMapLength}");
for (int i = 0; i < pkg.ExportsLazy.Length; i++)
{
    var obj = pkg.ExportsLazy[i].Value;
    Console.WriteLine($"  export[{i}] {obj?.GetType().FullName}");
    if (obj is UAkAudioEvent evt)
    {
        var lm = (System.Collections.IDictionary)evt.EventCookedData.GetType()
            .GetField("EventLanguageMap")!.GetValue(evt.EventCookedData)!;
        foreach (System.Collections.DictionaryEntry kv in lm)
        {
            var lang = kv.Key.GetType().GetField("LanguageName")!.GetValue(kv.Key);
            var cooked = kv.Value!;
            var media = (Array)cooked.GetType().GetField("Media")!.GetValue(cooked)!;
            for (int j = 0; j < media.Length; j++)
            {
                var m = media.GetValue(j)!;
                Console.WriteLine($"    {lang}[{j}] {m.GetType().Name}");
                foreach (var f in m.GetType().GetFields(BindingFlags.Public | BindingFlags.Instance))
                {
                    object v; try { v = f.GetValue(m); } catch { continue; }
                    Console.WriteLine($"       {f.Name} : {v?.GetType().Name} = {(v is string s ? s : (v is int or bool or uint ? v.ToString() : ""))}");
                }
            }
        }
    }
}
