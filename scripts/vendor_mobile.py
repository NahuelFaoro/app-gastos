"""Descarga dependencias fijadas para la PWA, sin dependencias CDN en ejecución."""
import io, json, tarfile, urllib.request, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] / "mobile" / "vendor"
ROOT.mkdir(parents=True, exist_ok=True)
packages = {"tesseract.js": "7.0.0", "tesseract.js-core": "7.0.0", "pdfjs-dist": "6.3.289"}
for name, version in packages.items():
    meta = json.load(urllib.request.urlopen(f"https://registry.npmjs.org/{name}/{version}"))
    blob = urllib.request.urlopen(meta["dist"]["tarball"]).read()
    assert hashlib.sha1(blob).hexdigest() == meta["dist"]["shasum"]
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile(): continue
            rel = member.name.removeprefix("package/")
            wanted = rel in ("LICENSE", "LICENSE.md", "LICENSE.txt")
            if name == "tesseract.js": wanted |= rel in ("dist/tesseract.esm.min.js", "dist/worker.min.js")
            if name == "tesseract.js-core": wanted |= rel.endswith(".wasm.js")
            if name == "pdfjs-dist": wanted |= rel in ("build/pdf.mjs", "build/pdf.worker.mjs") or rel.startswith(("wasm/", "standard_fonts/"))
            if wanted:
                target = ROOT / name / rel
                assert target.resolve().is_relative_to(ROOT.resolve())
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(member).read())
    print(name, version, flush=True)
lang = ROOT / "languages"; lang.mkdir(exist_ok=True)
lang.joinpath("spa.traineddata.gz").write_bytes(urllib.request.urlopen("https://cdn.jsdelivr.net/npm/@tesseract.js-data/spa@1.0.0/4.0.0_best_int/spa.traineddata.gz").read())
lang.joinpath("LICENSE").write_bytes(urllib.request.urlopen("https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/LICENSE").read())
(ROOT / "versions.json").write_text(json.dumps(packages, indent=2))
manifest = {str(p.relative_to(ROOT)).replace(chr(92), "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob("*") if p.is_file() and p.name != "sha256.json"}
(ROOT / "sha256.json").write_text(json.dumps(manifest, indent=2))
