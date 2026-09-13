from __future__ import annotations

"""Fachada estable para los diálogos de App Gastos.

Las implementaciones viven en ``app.dialog_modules`` por dominio. Este módulo
conserva la API histórica (``from app.dialogs import ...``) para que las páginas
no queden acopladas a la ubicación interna de cada diálogo.
"""

from .dialog_modules import *  # noqa: F401,F403
from .dialog_modules import __all__
