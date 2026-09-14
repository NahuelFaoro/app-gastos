"""Empaqueta un build OCR ya compilado, con guía, fuentes y licencias."""
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from app.constants import APP_VERSION


def main():
    root = Path(__file__).resolve().parents[1]
    bundle = root / "dist" / f"testers-v{APP_VERSION}"
    app = bundle / "AppGastos"
    assert (app / "AppGastos.exe").is_file(), "Primero compilar el ejecutable"
    assert len(list((app / "_internal" / "rapidocr" / "models").glob("*.onnx"))) >= 3, "Faltan modelos OCR"
    assert not any(p.suffix.lower() in (".db", ".sqlite", ".sqlite3") or p.name.startswith(".env") for p in app.rglob("*") if p.is_file()), "Hay datos ajenos al paquete"
    shutil.copyfile(root / "docs" / "GUIA_TESTERS.md", bundle / "LEEME.txt")
    licenses = bundle / "LICENCIAS"
    licenses.mkdir(exist_ok=True)
    versions = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        versions[name] = dist.version
        for item in dist.files or []:
            if any(word in str(item).lower() for word in ("license", "copying", "notice")):
                source = Path(dist.locate_file(item))
                if source.is_file():
                    target = licenses / name / Path(*[part for part in Path(str(item)).parts if part not in ("..", ".")])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copyfile(python_license, licenses / "PYTHON_LICENSE.txt")
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    paths += ["scripts/frozen_entry.py", "scripts/check_packaged_ocr.py", "scripts/package_testers.py", "scripts/build_testers.py", "docs/GUIA_TESTERS.md"]
    with ZipFile(bundle / "FUENTES.zip", "w", ZIP_DEFLATED) as archive:
        for name in sorted(set(paths)):
            if name and (root / name).is_file():
                assert not name.endswith((".db", ".sqlite", ".sqlite3")) and not Path(name).name.startswith(".env")
                archive.write(root / name, name)
    (bundle / "VERSIONES.json").write_text(json.dumps({"app": APP_VERSION, "dependencies": versions}, indent=2), encoding="utf-8")
    output = root / "dist" / f"AppGastos_v{APP_VERSION}_TESTERS_OCR.zip"
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(bundle))
    with ZipFile(output) as archive:
        assert archive.testzip() is None
    digest = hashlib.file_digest(output.open("rb"), "sha256").hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n", encoding="ascii")
    print(output)
    print(f"SIZE_MB={output.stat().st_size / 1024 / 1024:.1f}")
    print(f"SHA256={digest}")


if __name__ == "__main__":
    main()
