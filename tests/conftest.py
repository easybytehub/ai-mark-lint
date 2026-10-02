from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from ai_mark_lint.cli import main
from tests import fabrica

VERSIONADAS = Path(__file__).parent / "fixtures"
# El árbol que usan los tests vive en un directorio temporal: las fixtures versionadas
# se copian ahí, y `fabrica.genera` añade la CA de prueba y los ficheros firmados. La
# ruta se fija al importar para poder usarla en `parametrize`; el contenido lo pone la
# fixture de sesión `arbol_de_fixtures`, antes de que corra ningún test.
FIX = Path(tempfile.mkdtemp(prefix="ai-mark-lint-fixtures-"))
CA = FIX / "certs" / "ca.pem"


@pytest.fixture(scope="session", autouse=True)
def arbol_de_fixtures() -> Iterator[Path]:
    shutil.copytree(VERSIONADAS, FIX, dirs_exist_ok=True)
    fabrica.genera(FIX)
    yield FIX
    shutil.rmtree(FIX, ignore_errors=True)


def ejecuta(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    codigo = main([*argv, "--no-color"])
    salida = capsys.readouterr()
    return codigo, salida.out, salida.err
