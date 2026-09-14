"""Versiona caché y genera un ZIP estático publicable por HTTPS."""
import hashlib,json,re
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
root=Path(__file__).resolve().parents[1]
mobile=root/"mobile"
files=sorted(p for p in mobile.rglob("*") if p.is_file() and p.name not in ("precache.json","sw.js","README.md","_headers"))
sw_source=re.sub(r"const CACHE='[^']+';", "", (mobile/"sw.js").read_text(encoding="utf-8"))
revision=hashlib.sha256(sw_source.encode()+b"".join(p.read_bytes() for p in files)).hexdigest()[:12]
sw=mobile/"sw.js"
sw.write_text(re.sub(r"const CACHE='[^']+';",f"const CACHE='ag-independent-{revision}';",sw.read_text(encoding="utf-8")),encoding="utf-8")
(mobile/"precache.json").write_text(json.dumps([p.relative_to(mobile).as_posix() for p in files],indent=2),encoding="utf-8")
output=root/"dist"/"AppGastos_Movil_0.5.1_WEB.zip"
output.parent.mkdir(exist_ok=True)
with ZipFile(output,"w",ZIP_DEFLATED) as z:
 for p in mobile.rglob("*"):
  if p.is_file():
   assert p.suffix.lower() not in (".db",".sqlite",".sqlite3")
   z.write(p,p.relative_to(mobile))
with ZipFile(output) as z:assert z.testzip() is None
print(output)
print(f"{output.stat().st_size/1024/1024:.1f} MB")
