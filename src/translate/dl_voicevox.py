import urllib.request,os
u='https://github.com/VOICEVOX/voicevox_engine/releases/download/0.26.2/voicevox_engine-windows-cpu-0.26.2.7z.001'
dst='C:/Users/marou/AppData/Local/Temp/voicevox.7z.001'
os.makedirs(os.path.dirname(dst),exist_ok=True)
req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
with urllib.request.urlopen(req,timeout=120) as r, open(dst,'wb') as o:
    tot=0
    while True:
        b=r.read(1<<20)
        if not b: break
        o.write(b); tot+=len(b)
        if tot%(100<<20)<(1<<20): print(tot,flush=True)
print('DL DONE',tot,dst)
