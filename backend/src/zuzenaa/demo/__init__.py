"""Dataset ficticio y utilidades del modo demo.

Emula Classroom 50 en local (org ``ikastola-demo``) para ver ZuzenAA funcionando sin
tocar GitHub. Se activa con ``ZUZENAA_DEMO_MODE=true`` y se siembra con
``python -m zuzenaa.demo.seed``. Guía: ``docs/06-datos-de-prueba.md``.

Regla de oro: **nunca** activar el modo demo en producción.
"""

from __future__ import annotations

from pathlib import Path

from zuzenaa.config import settings

ORIGINS_DIRNAME = "demo-origins"


def origins_root() -> Path:
    """Carpeta con los repos git locales que hacen de «GitHub» ficticio."""
    return Path(settings.data_root) / ORIGINS_DIRNAME


def clone_url_template() -> str:
    """Plantilla de clonado ``file://`` que apunta a los orígenes locales."""
    return origins_root().as_uri() + "/{org}/{repo}"


__all__ = ["ORIGINS_DIRNAME", "clone_url_template", "origins_root"]
