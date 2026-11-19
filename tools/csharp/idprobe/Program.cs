using System;
using System.Collections.Generic;
using System.IO;
using CUE4Parse.UE4.IO.Objects;

// Checks that the chunk ids computed for a list of files are the ones the
// engine will actually resolve, by looking them up in the raw chunk id table
// of a reference container.
//
//   dotnet run -- <reference.utoc> <list of game paths>
//
// This is the regression test for the byte order of the package id: the
// engine writes it in native (little endian) order, so the table must be
// searched with little endian ids only. A big endian id set matches nothing
// and the game silently plays the original content.

var toc = args[0];
var list = args[1];

var bytes = File.ReadAllBytes(toc);
int entryCount = BitConverter.ToInt32(bytes, 24);
var ids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
for (int i = 0; i < entryCount; i++)
{
    ids.Add(Convert.ToHexString(bytes, 144 + i * 12, 12));
}

int hits = 0, total = 0;
var missing = new List<string>();
foreach (var line in File.ReadAllLines(list))
{
    var path = line.Split('\t')[0].Trim();
    if (path.Length == 0) continue;
    var ext = Path.GetExtension(path).ToLowerInvariant();
    var rel = path.Replace('\\', '/');
    const string prefix = "ProjectPBZ/Content/";
    if (rel.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) rel = rel.Substring(prefix.Length);
    var withoutExt = rel.Substring(0, rel.Length - ext.Length);

    var pkg = FPackageId.FromName("/Game/" + withoutExt);
    var id = new byte[12];
    for (int i = 0; i < 8; i++) id[i] = (byte)(pkg.id >> (8 * i));
    id[11] = (byte)(ext == ".ubulk" ? 2 : 1);

    var hex = Convert.ToHexString(id).ToLowerInvariant();
    if (ids.Contains(hex)) hits++;
    else if (missing.Count < 10) missing.Add($"{path} -> {hex}");
    total++;
}

Console.WriteLine($"{hits}/{total} chunk ids resolve against {Path.GetFileName(toc)}");
foreach (var m in missing) Console.WriteLine("  missing: " + m);
return hits == total ? 0 : 1;
