"""Build Windows completo, prueba del binario y ZIP para testers."""
import os
import subprocess
import sys
from pathlib import Path
from app.constants import APP_VERSION


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / "dist" / f"testers-v{APP_VERSION}"
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir", "--name", "AppGastos", "--paths", str(root), "--distpath", str(target), "--workpath", str(root / "build" / f"testers-v{APP_VERSION}"), "--specpath", str(root / "build"), "--add-data", f"{root / 'web'};web", "--collect-data", "qtawesome", "--collect-all", "rapidocr", "--hidden-import", "onnxruntime", "--collect-all", "onnxruntime"]
    for module in ("PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "torch", "paddle", "tensorflow"):
        command.extend(("--exclude-module", module))
    command.append(str(root / "scripts" / "frozen_entry.py"))
    # Evita recoger DLL de herramientas ajenas al proyecto presentes en PATH.
    build_env = dict(os.environ)
    system = Path(os.environ["SystemRoot"])
    build_env["PATH"] = os.pathsep.join(map(str, (system / "System32", system, Path(sys.base_prefix), Path(sys.base_prefix) / "DLLs", Path(sys.prefix) / "Scripts")))
    subprocess.run(command, cwd=root, env=build_env, check=True)
    executable = target / "AppGastos" / "AppGastos.exe"
    for mode in ("--self-test", "--ocr-self-test"):
        log = root / "dist" / (mode.strip("-") + ".log")
        env = dict(os.environ)
        env.update(HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9")
        subprocess.run([str(executable), mode, str(log)], cwd=target, env=env, check=True, timeout=240, creationflags=subprocess.CREATE_NO_WINDOW)
        text = log.read_text(encoding="utf-8")
        marker = "APP_GASTOS_PACKAGED_OCR_OK" if mode == "--ocr-self-test" else "APP_GASTOS_SMOKE_OK"
        assert marker in text, text
        print(text)
    from scripts.package_testers import main as package
    package()


if __name__ == "__main__":
    main()
