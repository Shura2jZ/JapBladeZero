using System;
using System.Collections.Generic;
using System.IO;
using CUE4Parse.UE4.IO.Objects;

// Computes the IoStore chunk id of every file of a list.
//
//   dotnet run -- <list of game paths> [output]
//
// The chunk id is the 12 byte identifier used by the containers: the package id
// (8 bytes), the chunk index (2 bytes), a padding byte and the chunk type
// (1 = export bundle, 2 = bulk data).

var files = args[0];
var outFile = args.Length > 1 ? args[1] : null;
using var w = outFile != null ? new StreamWriter(outFile) : null;
foreach (var line in File.ReadAllLines(files))
{
    var path = line.Trim();
    if (path.Length == 0) continue;
    var ext = Path.GetExtension(path).ToLowerInvariant();
    var rel = path.Replace(Path.DirectorySeparatorChar, '/');
    const string prefix = "ProjectPBZ/Content/";
    if (rel.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) rel = rel.Substring(prefix.Length);
    var withoutExt = rel.Substring(0, rel.Length - ext.Length);
    var pkgPath = "/Game/" + withoutExt;
    var packageId = FPackageId.FromName(pkgPath);
    byte type = ext == ".ubulk" ? (byte)2 : (byte)1;
    var id = new byte[12];
    for (int i = 0; i < 8; i++) id[i] = (byte)(packageId.id >> (56 - 8 * i));
    id[11] = type;
    Console.WriteLine($"{path}\t{Convert.ToHexString(id).ToLowerInvariant()}\t{pkgPath}");
    w?.WriteLine($"{path}\t{Convert.ToHexString(id).ToLowerInvariant()}\t{pkgPath}");
}
w?.Close();
