from __future__ import annotations

"""Validación rápida para desarrollo sin abrir la interfaz gráfica.

Uso desde la raíz del proyecto:
    python scripts/validate_project.py
"""

import compileall
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print("[1/3] Auditando arquitectura...")
    audit_result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_architecture.py")],
        cwd=ROOT,
        check=False,
    )
    if audit_result.returncode:
        return audit_result.returncode

    print("[2/3] Compilando módulos Python...")
    ok = compileall.compile_dir(ROOT / "app", quiet=1)
    ok = compileall.compile_file(ROOT / "main.py", quiet=1) and ok
    ok = compileall.compile_file(ROOT / "scripts" / "check_app.py", quiet=1) and ok
    if not ok:
        print("Falló la compilación sintáctica.", file=sys.stderr)
        return 1

    print("[3/3] Ejecutando pruebas unitarias...")
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        check=False,
    )
    if result.returncode:
        return result.returncode

    print("VALIDATION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
