from __future__ import annotations

"""Chequeos estructurales que previenen regresiones de arquitectura.

No reemplaza tests funcionales. Su objetivo es detectar rápidamente patrones
que históricamente hicieron que un cambio local afectara módulos no relacionados:
SQL en vistas, reglas de calendario duplicadas, estilos redefinidos y un
repositorio SQLite monolítico.
"""

import ast
import builtins
import re
import symtable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"


def _python_files(folder: Path):
    return sorted(folder.rglob("*.py"))


def _duplicate_qss_selectors() -> list[str]:
    source = (APP / "style_rules.py").read_text(encoding="utf-8")
    try:
        start = source.index('qss = f"""') + len('qss = f"""')
        end = source.index('"""\n    return _scale_qss_pixels', start)
    except ValueError:
        return ["No se pudo localizar el template QSS de style_rules.py"]
    qss = source[start:end]
    pattern = re.compile(r"(?m)^\s*([^/\n][^\n]*?)\s*\{\{")
    counts: dict[str, int] = {}
    for match in pattern.finditer(qss):
        for selector in (part.strip() for part in match.group(1).split(",")):
            if selector:
                counts[selector] = counts.get(selector, 0) + 1
    return sorted(selector for selector, count in counts.items() if count > 1)


def _relative_import_errors() -> list[str]:
    """Valida imports relativos sin importar PySide6 ni ejecutar la aplicación.

    Este chequeo existe porque mover módulos grandes a subpaquetes puede dejar
    un ``..foo`` apuntando a un paquete distinto. Python compila ese archivo,
    pero el fallo recién aparece al importarlo en runtime.
    """
    errors: list[str] = []
    for path in _python_files(APP):
        rel = path.relative_to(ROOT)
        module_parts = list(rel.with_suffix("").parts)
        if module_parts[-1] == "__init__":
            module_parts = module_parts[:-1]
            package_parts = module_parts
        else:
            package_parts = module_parts[:-1]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            up = node.level - 1
            if up > len(package_parts):
                errors.append(f"{rel}:{node.lineno} intenta importar fuera del paquete app")
                continue
            target_parts = package_parts[: len(package_parts) - up]
            if node.module:
                target_parts += node.module.split(".")
            target = ROOT.joinpath(*target_parts)
            if not (target.with_suffix(".py").exists() or (target / "__init__.py").exists()):
                dotted = ".".join(target_parts) or "<raíz>"
                errors.append(f"{rel}:{node.lineno} apunta a módulo relativo inexistente: {dotted}")
    return errors



def _undefined_global_names() -> list[str]:
    """Detecta nombres globales usados sin import/definición.

    ``compileall`` sólo valida sintaxis: un helper olvidado al mover un método
    (por ejemplo ``add_months``) recién falla al ejecutar esa rama. ``symtable``
    permite detectar ese desacople sin importar PySide6 ni ejecutar la UI.
    """
    errors: list[str] = []
    allowed = set(dir(builtins)) | {
        "__file__", "__name__", "__package__", "__doc__", "__annotations__",
        "__spec__", "__loader__", "__cached__",
    }
    for path in _python_files(APP):
        source = path.read_text(encoding="utf-8")
        table = symtable.symtable(source, str(path), "exec")
        module_names = {symbol.get_name() for symbol in table.get_symbols()}
        missing: set[str] = set()

        def walk(scope) -> None:
            for symbol in scope.get_symbols():
                name = symbol.get_name()
                if symbol.is_referenced() and symbol.is_global() and name not in module_names and name not in allowed:
                    missing.add(name)
            for child in scope.get_children():
                walk(child)

        walk(table)
        if missing:
            errors.append(f"{path.relative_to(ROOT)} usa globales no definidos/importados: {', '.join(sorted(missing))}")
    return errors


def _internal_import_cycles() -> list[list[str]]:
    """Detecta ciclos de imports internos de primer nivel entre módulos ``app``."""
    modules: dict[str, Path] = {}
    for path in _python_files(APP):
        parts = list(path.relative_to(ROOT).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules[".".join(parts)] = path

    graph: dict[str, set[str]] = {name: set() for name in modules}
    for name, path in modules.items():
        package = name.split(".") if path.name == "__init__.py" else name.split(".")[:-1]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    up = node.level - 1
                    base = package[: len(package) - up]
                    if node.module:
                        base += node.module.split(".")
                    targets = [".".join(base)]
                elif node.module:
                    targets = [node.module]
            for target in targets:
                if target in modules:
                    graph[name].add(target)

    cycles: set[tuple[str, ...]] = set()
    visiting: list[str] = []
    active: set[str] = set()
    done: set[str] = set()

    def walk(node: str) -> None:
        if node in done:
            return
        if node in active:
            try:
                start = visiting.index(node)
            except ValueError:
                return
            cycle = visiting[start:]
            if cycle:
                rotations = [tuple(cycle[i:] + cycle[:i]) for i in range(len(cycle))]
                cycles.add(min(rotations))
            return
        active.add(node)
        visiting.append(node)
        for child in graph[node]:
            walk(child)
        visiting.pop()
        active.remove(node)
        done.add(node)

    for module in graph:
        walk(module)
    return [list(cycle) for cycle in sorted(cycles)]

def _long_functions() -> list[tuple[int, str, str]]:
    result: list[tuple[int, str, str]] = []
    for path in _python_files(APP):
        if path.name == "style_rules.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = int(getattr(node, "end_lineno", node.lineno)) - node.lineno + 1
                if length >= 120:
                    result.append((length, str(path.relative_to(ROOT)), node.name))
    return sorted(result, reverse=True)


def audit() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []

    db_lines = len((APP / "db.py").read_text(encoding="utf-8").splitlines())
    if db_lines > 1800:
        errors.append(f"app/db.py volvió a crecer demasiado ({db_lines} líneas; máximo 1800).")

    expected_repositories = {
        "accounts.py", "analytics.py", "categories.py", "flex.py", "import_queue.py",
        "installments.py", "planning.py", "transactions.py", "work_config.py", "work_tracking.py",
    }
    actual = {path.name for path in (APP / "repositories").glob("*.py")}
    missing = sorted(expected_repositories - actual)
    if missing:
        errors.append("Faltan repositorios de dominio: " + ", ".join(missing))

    duplicate_selectors = _duplicate_qss_selectors()
    if duplicate_selectors:
        errors.append(
            "Hay selectores QSS redefinidos, lo que vuelve impredecibles los cambios visuales: "
            + ", ".join(duplicate_selectors[:12])
        )

    relative_import_errors = _relative_import_errors()
    if relative_import_errors:
        errors.extend("Import relativo inválido: " + item for item in relative_import_errors)

    undefined_globals = _undefined_global_names()
    if undefined_globals:
        errors.extend("Nombre global sin resolver: " + item for item in undefined_globals)

    internal_cycles = _internal_import_cycles()
    if internal_cycles:
        errors.extend("Ciclo de imports internos: " + " -> ".join(cycle + [cycle[0]]) for cycle in internal_cycles)

    # Las vistas coordinan UI; persistencia SQL sólo vive en db/repositorios.
    for path in _python_files(APP / "pages"):
        source = path.read_text(encoding="utf-8")
        if "sqlite3" in source or ".execute(" in source or "executescript(" in source:
            errors.append(f"Persistencia/SQL detectada dentro de una vista: {path.relative_to(ROOT)}")

    # Una única regla semanal evita volver a mezclar semanas de 5 y 7 días.
    calendar_source = (APP / "work_calendar.py").read_text(encoding="utf-8")
    if "WORK_WEEK_DAYS = 7" not in calendar_source:
        errors.append("work_calendar.py debe ser la fuente de verdad de la semana de 7 días.")
    for path in [
        APP / "pages" / "viajes.py",
        APP / "pages" / "viajes_dialogs.py",
        APP / "pages" / "viajes_widgets.py",
        APP / "pages" / "extras_widgets.py",
    ]:
        source = path.read_text(encoding="utf-8")
        if "range(7)" in source or "timedelta(days=6)" in source:
            errors.append(f"Hardcode semanal duplicado en {path.relative_to(ROOT)}")

    long_functions = _long_functions()
    if long_functions:
        notes.append(
            "Funciones >=120 líneas restantes (candidatas a refactor futuro): "
            + ", ".join(f"{path}:{name}({length})" for length, path, name in long_functions[:10])
        )

    return errors, notes


def main() -> int:
    errors, notes = audit()
    for note in notes:
        print("AUDIT_NOTE:", note)
    if errors:
        for error in errors:
            print("AUDIT_ERROR:", error)
        return 1
    print("ARCHITECTURE_AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
