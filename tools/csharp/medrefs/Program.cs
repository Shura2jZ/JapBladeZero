using CUE4Parse.Compression;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Assets.Exports.Wwise;
using System.Reflection;

// Lists the media referenced by every voice event, with the Wwise media id, the debug
// name of the source file, the hash and the packaging strategy.
//
//   dotnet run -- --events <file> [--out <file>]
//
// Output: one line per media
//   event <TAB> language <TAB> mediaId <TAB> hash <TAB> strategy <TAB> debugName

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

string eventsFile = null, outFile = null;
for (int i = 0; i < args.Length; i++)
{
    if (args[i] == "--events") eventsFile = args[++i];
    if (args[i] == "--out") outFile = args[++i];
}

var events = File.ReadAllLines(eventsFile).Select(l => l.Trim()).Where(l => l.Length > 0).ToList();
var sw = new StreamWriter(outFile ?? "media_refs.tsv") { AutoFlush = false };
sw.WriteLine("event\tlang\tmediaId\thash\tstrategy\tdebugName");

foreach (var ev in events)
{
    var key = provider.Files.Keys.FirstOrDefault(k => k.EndsWith("/" + ev + ".uasset", StringComparison.OrdinalIgnoreCase));
    if (key is null) { Console.WriteLine($"! {ev} not found"); continue; }
    var pk = provider.LoadPackage(provider.Files[key]) as IoPackage;
    if (pk is null) { Console.WriteLine($"! {ev} not an IoPackage"); continue; }
    foreach (var exp in pk.ExportsLazy)
    {
        if (exp.Value is not UAkAudioEvent evt) continue;
        var langMap = evt.EventCookedData.GetType().GetField("EventLanguageMap")!.GetValue(evt.EventCookedData)! as System.Collections.IDictionary;
        foreach (System.Collections.DictionaryEntry kv in langMap)
        {
            var lang = kv.Key.GetType().GetField("LanguageName")!.GetValue(kv.Key)?.ToString();
            var mediaArr = kv.Value!.GetType().GetField("Media")!.GetValue(kv.Value!) as Array;
            for (int i = 0; i < (mediaArr?.Length ?? 0); i++)
            {
                var m = mediaArr!.GetValue(i)!;
                var pf = m.GetType().GetField("PackagedFile")!.GetValue(m)!;
                var id = m.GetType().GetField("MediaId")!.GetValue(m);
                var dbg = m.GetType().GetField("DebugName")!.GetValue(m);
                var hashn = pf.GetType().GetField("Hash")?.GetValue(pf);
                var strat = pf.GetType().GetField("PackagingStrategy")?.GetValue(pf);
                var path = pf.GetType().GetField("PathName")?.GetValue(pf);
                sw.WriteLine($"{ev}\t{lang}\t{id}\t{hashn}\t{strat}\t{path}\t{dbg}");
            }
        }
    }
}
sw.Flush();
sw.Close();
Console.WriteLine($"wrote {outFile}");
