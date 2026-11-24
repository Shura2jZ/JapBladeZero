using CUE4Parse.UE4.IO;
using CUE4Parse.UE4.IO.Objects;
using CUE4Parse.UE4.Versions;
using System.Reflection;

// Walks the IoStore containers (the .utoc files) and reports the chunks whose id
// carries one of the given 32 bit hashes (the Wwise media hashes).
//
//   dotnet run -- --paks <dir> --hashes <file> [--dump <file>]
//
// The hash file holds one 32 bit hash per line. For every container the tool prints
// the chunks matching, with their type, their offset and their length, so the media
// of the Wwise library can be located by hash instead of by guesswork.

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

var versions = new VersionContainer(EGame.GAME_PhantomBladeZero);
string paks = cfg["paks"], hashesFile = null, dumpFile = null, sizesFile = null;
string name = cfg.TryGetValue("name", out var n) ? n : null;
for (int i = 0; i < args.Length; i++)
{
    if (args[i] == "--paks") paks = args[++i];
    if (args[i] == "--hashes") hashesFile = args[++i];
    if (args[i] == "--dump") dumpFile = args[++i];
    if (args[i] == "--sizes") sizesFile = args[++i];
    if (args[i] == "--name") name = args[++i];
}

var wanted = new HashSet<uint>();
if (hashesFile != null)
    foreach (var l in File.ReadAllLines(hashesFile)) { if (uint.TryParse(l.Trim(), out var h)) wanted.Add(h); }
Console.WriteLine($"{wanted.Count} hashes to look for");

var sw = dumpFile != null ? new StreamWriter(dumpFile) : null;
foreach (var tocPath in Directory.GetFiles(paks, "*.utoc").OrderBy(p => p))
{
    if (!string.IsNullOrEmpty(name) && !Path.GetFileName(tocPath).StartsWith(name, StringComparison.OrdinalIgnoreCase)) continue;
    IoStoreReader reader;
    try { reader = new IoStoreReader(tocPath, EIoStoreTocReadOptions.Default, versions); }
    catch (Exception e) { Console.WriteLine($"{Path.GetFileName(tocPath)}: cannot open ({e.GetType().Name})"); continue; }
    var toc = reader.TocResource;
    Console.WriteLine($"{Path.GetFileName(tocPath)}: {toc.ChunkIds.Length} chunks, {toc.ChunkOffsetLengths.Length} offsets");
    int found = 0;
    if (dumpFile != null && args.Contains("--all"))
    {
        sw?.WriteLine("index	id	type	chunkIndex	offset	length	hash");
        for (int i = 0; i < toc.ChunkIds.Length; i++)
        {
            var cid = toc.ChunkIds[i];
            var ol = toc.ChunkOffsetLengths[i];
            var meta = toc.ChunkMetas != null && i < toc.ChunkMetas.Length ? toc.ChunkMetas[i] : default;
            sw?.WriteLine($"{i}	{cid.ChunkId}	{cid.ChunkType}	{cid._chunkIndex}	{ol.Offset}	{ol.Length}	{meta.ChunkHash}");
        }
        sw?.WriteLine($"# compression_blocks	{toc.CompressionBlocks?.Length ?? 0}");
        for (int i = 0; toc.CompressionBlocks != null && i < toc.CompressionBlocks.Length; i++)
        {
            var cb = toc.CompressionBlocks[i];
            sw?.WriteLine($"cb	{i}	{cb.Offset}	{cb.CompressedSize}	{cb.UncompressedSize}	{cb.CompressionMethodIndex}");
        }
        sw?.WriteLine("# compression_methods	" + (toc.CompressionMethods != null ? string.Join(",", toc.CompressionMethods.Select(m => m.ToString())) : ""));
        sw?.WriteLine($"# header	version={toc.Header.Version}	entries={toc.Header.TocEntryCount}	blocks={toc.Header.TocCompressedBlockEntryCount}	blocksize={toc.Header.TocCompressedBlockEntrySize}	methodcount={toc.Header.CompressionMethodNameCount}	methodlen={toc.Header.CompressionMethodNameLength}	comprblk={toc.Header.CompressionBlockSize}	diridx={toc.Header.DirectoryIndexSize}	partitioncount={toc.Header.PartitionCount}	partitionsize={toc.Header.PartitionSize}	headersize={toc.Header.TocHeaderSize}	seeds={toc.Header.TocChunkPerfectHashSeedsCount}	noperfect={toc.Header.TocChunksWithoutPerfectHashCount}");
    }
    if (sizesFile != null)
    {
        var sizes = new HashSet<long>(File.ReadAllLines(sizesFile).Select(l => long.Parse(l.Trim())).Where(l => l > 0));
        int m = 0;
        for (int i = 0; i < toc.ChunkIds.Length; i++)
        {
            var ol = toc.ChunkOffsetLengths[i];
            if (!sizes.Contains((long)ol.Length)) continue;
            m++;
            if (m <= 20) Console.WriteLine($"   SIZE chunk {i} len={ol.Length} offset={ol.Offset} type={toc.ChunkIds[i].ChunkType}");
        }
        Console.WriteLine($"   {m} chunks match a requested size");
    }
    for (int i = 0; i < toc.ChunkIds.Length; i++)
    {
        var cid = toc.ChunkIds[i];
        uint low = (uint)(cid.ChunkId & 0xFFFFFFFF);
        uint high = (uint)(cid.ChunkId >> 32);
        if (!wanted.Contains(low) && !wanted.Contains(high)) continue;
        found++;
        var ol = toc.ChunkOffsetLengths[i];
        var meta = toc.ChunkMetas != null && i < toc.ChunkMetas.Length ? toc.ChunkMetas[i] : default;
        Console.WriteLine($"   HIT chunk {i} id=0x{cid.ChunkId:X16} type={cid.ChunkType} index={cid._chunkIndex} offset={ol.Offset} len={ol.Length} chunkhash={meta.ChunkHash}");
        sw?.WriteLine($"{toc.ChunkIds[i].ChunkId}\t{toc.ChunkIds[i].ChunkType}\t{ol.Offset}\t{ol.Length}\t{meta.ChunkHash}");
    }
    Console.WriteLine($"   {found} hits");
    sw?.Flush();
}
sw?.Close();
