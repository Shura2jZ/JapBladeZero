"""Vérifie qu'un conteneur IoStore est complet et que le moteur UE pourra le monter.

Le moteur ne résout un paquet qu'après avoir lu l'**en-tête du conteneur** (chunk
de type 6, `ContainerHeader`), qui porte la liste des package ids : c'est le
« package store ». Cet en-tête est écrit en dernier, à la fin des données.

Si le fichier `.ucas` est tronqué (disque plein pendant la construction, copie
interrompue...), le `.utoc` continue de décrire des données absentes du fichier :

  * le montage ne signale aucune erreur,
  * l'en-tête est illisible, donc aucun package id n'est enregistré,
  * le moteur joue le contenu original — les voix restent chinoises.

C'est exactement le bug qui a été-shippé le 20/11 : le `.ucas` faisait 1,15 Go pour
1,54 Go décrits par le `.utoc`.

Les offsets des chunks sont des offsets **logiques** : ils désignent une position
dans l'espace des blocs de compression (offset du bloc + décalage dans le bloc),
et non un octet du fichier. C'est la table des blocs qui donne la position
réelle sur le disque. Comparer directement `offset + longueur` à la taille du
`.ucas` est donc faux : le contrôle se fait sur la table des blocs.

Ce contrôle refuse un conteneur incomplet. Usage :

    python src/patch/check_container.py E:/PBZ_Mod [ProjectPBZ-JapaneseVoice]
"""
import argparse
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import BASE

CHUNKMAP = os.path.join(BASE, 'tools', 'csharp', 'chunkmap', 'bin', 'Release', 'net10.0', 'chunkmap.dll')
# FIoContainerHeader::Signature
HEADER_SIGNATURE = 0x496F436E
# EIoChunkType::ContainerHeader
CHUNK_TYPE_CONTAINER_HEADER = 6


def dump_toc(container_dir, name):
    """Dump du TOC du conteneur : index, id, type, index de chunk, offset, longueur."""
    with open(os.devnull, 'w') as devnull:
        dump = os.path.join(container_dir, '_toc_dump.tsv')
        hashes = os.path.join(container_dir, '_hashes.txt')
        open(hashes, 'w').close()
        cmd = ['dotnet', CHUNKMAP, '--paks', container_dir, '--name', name, '--dump', dump, '--hashes', hashes, '--all']
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not os.path.exists(dump):
            print(res.stdout[-1500:])
            print(res.stderr[-1500:])
            return None
        rows = []
        blocks = []
        chunk_ids = []
        for line in open(dump, encoding='utf-8', errors='replace'):
            f = line.rstrip('\n').split('\t')
            if f[0] == 'cb':
                # cb <index> <offset sur disque> <taille compressee> <taille decompressee> <methode>
                try:
                    blocks.append((int(f[2]), int(f[3])))
                except ValueError:
                    pass
                continue
            if len(f) < 6 or f[0] == 'index':
                continue
            try:
                chunk_type, offset, length = int(f[2]), int(f[4]), int(f[5])
            except ValueError:
                continue
            # le dump contient aussi les blocs de compression : on ne garde que
            # les types de chunk (EIoChunkType, 1 a 13)
            if 1 <= chunk_type <= 13:
                rows.append((chunk_type, offset, length))
                chunk_ids.append((f[1], chunk_type))
        os.remove(dump)
        os.remove(hashes)
        return rows, blocks, chunk_ids


def read_header_package_ids(ucas, offset, count):
    """Lit les package ids declares par l'en-tete du conteneur (FPackageId, 8 octets)."""
    ids = set()
    with open(ucas, 'rb') as f:
        f.seek(offset + 20)  # signature (4) + version (4) + container id (8) + compte (4)
        for _ in range(count):
            raw = f.read(8)
            if len(raw) < 8:
                break
            ids.add(raw.hex())
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir', help='directory of the container')
    ap.add_argument('name', nargs='?', default='ProjectPBZ-JapaneseVoice')
    args = ap.parse_args()

    ucas = os.path.join(args.dir, args.name + '.ucas')
    utoc = os.path.join(args.dir, args.name + '.utoc')
    for p in (ucas, utoc):
        if not os.path.exists(p):
            print('KO : fichier absent', p)
            return 1

    size = os.path.getsize(ucas)
    dumped = dump_toc(args.dir, args.name)
    if not dumped:
        print('KO : le .utoc est illisible')
        return 1
    rows, blocks, chunk_ids = dumped

    errors = []
    # Un conteneur qui ne contient pas tous les paquets patches est monte
    # sans erreur, mais le jeu joue alors l'original pour les absents.
    MIN_CHUNKS = 7000
    if len(rows) < MIN_CHUNKS:
        errors.append('le conteneur ne contient que %d chunks (attendu au moins %d) : '
                      "l'injection n'a probablement pas ete complete"
                      % (len(rows), MIN_CHUNKS))
    # La fin reelle du fichier se deduit de la table des blocs : c'est elle qui
    # donne la position sur le disque de chaque bloc de compression.
    disk_end = max((off + size for off, size in blocks), default=0)
    if disk_end > size:
        errors.append('la table des blocs demande %d octets, le .ucas n\'en fait que %d '
                      ': le conteneur est tronque' % (disk_end, size))

    # L'index du bloc qui contient un offset logique est l'offset divise par la
    # taille du bloc de compression : c'est ainsi que le moteur y accede.
    block_size = 65536

    def block_of(logical_offset):
        return logical_offset // block_size

    beyond = []
    for chunk_type, offset, length in rows:
        idx = block_of(offset)
        if idx < 0 or idx >= len(blocks):
            beyond.append((chunk_type, offset, length))
        elif blocks[idx][0] + blocks[idx][1] > size:
            beyond.append((chunk_type, offset, length))
    if beyond:
        first = min(beyond, key=lambda r: r[1])
        errors.append('%d chunks (%d Mo) sont dans des blocs absents du .ucas : '
                      'le premier commence a %d, le .ucas fait %d octets'
                      % (len(beyond), sum(r[2] for r in beyond) // 10 ** 6, first[1], size))
    end = max((r[1] for r in rows), default=0)

    headers = [r for r in rows if r[0] == CHUNK_TYPE_CONTAINER_HEADER]
    if not headers:
        errors.append("le chunk d'en-tete du conteneur (type 6) est absent : "
                      'le moteur ne pourra resoudre aucun paquet')
    else:
        off, ln = headers[0][1], headers[0][2]
        idx = block_of(off)
        if idx < 0 or idx >= len(blocks):
            errors.append("l'en-tete du conteneur (offset logique %d) est hors de tout "
                          'bloc de compression' % off)
        else:
            block_off, block_size_on_disk = blocks[idx]
            if block_off + block_size_on_disk > size:
                errors.append("l'en-tete du conteneur est dans un bloc absent du .ucas "
                              '(bloc a %d, fichier de %d octets)' % (block_off, size))
            else:
                with open(ucas, 'rb') as f:
                    f.seek(block_off + (off % block_size))
                    head = f.read(min(ln, 32))
                sig, version = struct.unpack_from('<II', head, 0)
                if sig != HEADER_SIGNATURE:
                    errors.append("signature d'en-tete invalide (0x%08X au lieu de 0x%08X)"
                                  % (sig, HEADER_SIGNATURE))
                else:
                    # signature (4) + version (4) + container id (8) + nombre de paquets (4)
                    count = struct.unpack_from('<i', head, 16)[0]
                    if count <= 0:
                        errors.append("l'en-tete ne declare aucun paquet (%d)" % count)
                    else:
                        print('en-tete du conteneur : version %d, %d paquets' % (version, count))

                        # Verification decisive : les package ids de l'en-tete doivent
                        # etre ceux des chunks du TOC. C'est ce que le moteur
                        # resout : s'ils different, le conteneur est monte mais
                        # aucun paquet n'est trouve, et le jeu joue l'original.
                        header_pkg_ids = read_header_package_ids(
                            ucas, block_off + (off % block_size), count)
                        toc_pkg_ids = set()
                        for cid, cid_type in chunk_ids:
                            # CUE4Parse sort l'identifiant de paquet sous forme
                            # d'entier : il correspond aux 8 octets du package id
                            # en ordre natif (little endian).
                            if cid_type == CHUNK_TYPE_CONTAINER_HEADER:
                                continue  # l'en-tete lui-meme n'appartient pas au store
                            toc_pkg_ids.add(int(cid).to_bytes(8, 'little').hex())
                        missing = toc_pkg_ids - header_pkg_ids
                        extra = header_pkg_ids - toc_pkg_ids
                        if missing:
                            errors.append('%d package ids du TOC sont absents de l\'en-tete '
                                          'du conteneur : le moteur ne resolvra pas ces '
                                          'paquets' % len(missing))
                        if extra:
                            errors.append("%d package ids de l'en-tete ne correspondent a "
                                          'aucun chunk du TOC' % len(extra))
                        if not missing and not extra:
                            print('package ids : %d ids du TOC, tous presents dans '
                                  'l\'en-tete -> le moteur resolvra ces paquets'
                                  % len(toc_pkg_ids))

    print('conteneur : %d chunks, %d blocs, donnees sur disque jusqu\'a %d octets, '
          '.ucas de %d octets' % (len(rows), len(blocks), disk_end, size))
    if errors:
        print('\nKO : le conteneur est incomplet')
        for e in errors:
            print('  -', e)
        return 1
    print('OK : le conteneur est complet')
    return 0


if __name__ == '__main__':
    sys.exit(main())
