"""La interfaz de línea de comandos (en inglés: es para un público global).

**El código de salida es la parte que importa.** `1` cuando hay errores, `0` cuando no,
`2` cuando la herramienta no ha podido hacer su trabajo. Los avisos y lo indeterminado
no fallan por defecto; `--strict` está para quien quiera lo contrario.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from ai_mark_lint import __version__
from ai_mark_lint.catalogo import REGLAS
from ai_mark_lint.comparacion import compara
from ai_mark_lint.hallazgos import Hallazgo, Informe
from ai_mark_lint.lector_c2pa import AnclasInvalidas, contexto
from ai_mark_lint.marcas import FormatoNoSoportado, Marcas, inventaria
from ai_mark_lint.reglas import audita
from ai_mark_lint.salida import como_json, como_sarif, texto

JURISDICCIONES = ("eu", "ca", "cn")
POR_DEFECTO = "eu,ca"

EPILOGO = """\
ai-mark-lint reads the provenance metadata of files that already exist (C2PA,
IPTC DigitalSourceType in XMP and the GB 45438-2025 AIGC implicit label) and checks it
against EU AI Act art. 50(2), the California AI Transparency Act and China's labelling
rules. Give it files your system generated or manipulated with AI: on a file that is
not synthetic its findings make no sense.

It does not detect invisible watermarks or deepfakes (art. 50(4)), and it does not tell
whether content is synthetic: it reads what the file declares about itself. It never
goes to the network.

China (cn) is not a default jurisdiction: it is the only one where a missing label is
an error, and it only binds services provided in China.

Exit codes: 0 no errors; 1 errors (or warnings with --strict); 2 the tool could not do
its job. A clean result does not certify compliance.
"""


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ai-mark-lint",
        description="Check the machine-readable AI marks of images, video and audio.",
        epilog=EPILOGO,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "files", nargs="*", type=Path, help="JPEG, PNG, WebP, AVIF/HEIF, MP4/MOV, MP3, WAV"
    )
    p.add_argument(
        "--jurisdiction",
        default=POR_DEFECTO,
        help=f"comma-separated list of {', '.join(JURISDICCIONES)} (default: {POR_DEFECTO}); "
        "'none' keeps only the technical rules",
    )
    p.add_argument("--format", choices=("text", "json", "sarif"), default="text")
    p.add_argument("--strict", action="store_true", help="exit with 1 on warnings too")
    p.add_argument("--before", type=Path, metavar="A", help="original file (compare mode)")
    p.add_argument("--after", type=Path, metavar="B", help="the same file after your pipeline")
    p.add_argument(
        "--trust-anchors",
        type=Path,
        metavar="PEM",
        help="root certificates (PEM) to evaluate trust in the C2PA signer",
    )
    p.add_argument("--no-color", action="store_true", help="disable colour")
    p.add_argument("--version", action="version", version=f"ai-mark-lint {__version__}")
    return p.parse_args(argv)


def _jurisdicciones(valor: str) -> tuple[str, ...]:
    if valor.strip().lower() in ("none", ""):
        return ()
    js = tuple(dict.fromkeys(j.strip().lower() for j in valor.split(",") if j.strip()))
    malas = [j for j in js if j not in JURISDICCIONES]
    if malas:
        raise ValueError(f"unknown jurisdiction: {', '.join(malas)}")
    return js


def _error(msg: str) -> int:
    print(f"ai-mark-lint: {msg}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    try:
        return _ejecuta(args)
    except Exception as exc:  # red de seguridad: nunca una traza en CI
        # Un fallo interno no es un hallazgo: es la herramienta que no ha podido hacer su
        # trabajo, y eso es la salida 2, con una línea que se pueda pegar en un issue.
        return _error(f"internal error: {type(exc).__name__}: {exc}".splitlines()[0])


def _ejecuta(args: argparse.Namespace) -> int:
    try:
        jurisdicciones = _jurisdicciones(args.jurisdiction)
    except ValueError as exc:
        return _error(str(exc))

    comparando = args.before is not None or args.after is not None
    if comparando and (args.before is None or args.after is None or args.files):
        return _error("--before and --after go together and without other files")
    if not comparando and not args.files:
        return _error("give at least one file, or --before A --after B")

    anclas: str | None = None
    if args.trust_anchors is not None:
        try:
            anclas = args.trust_anchors.read_text(encoding="utf-8")
            contexto(anclas)  # se valida antes de leer ningún fichero
        except OSError as exc:
            return _error(f"{args.trust_anchors}: {exc.strerror or exc}")
        except (UnicodeDecodeError, AnclasInvalidas) as exc:
            return _error(f"invalid trust anchors: {args.trust_anchors}: {exc}")
        except ImportError:
            return _error("--trust-anchors needs c2pa-python, which is not available")

    ilegibles: list[str] = []

    def lee(ruta: Path) -> Marcas | str | None:
        """Las marcas; None si el formato no se soporta; un texto si no se puede leer."""
        if not ruta.is_file():
            return "does not exist or is not a regular file"
        try:
            return inventaria(ruta, anclas)
        except FormatoNoSoportado:
            return None
        except OSError as exc:  # permisos, E/S
            return exc.strerror or str(exc)

    hallazgos: list[Hallazgo] = []
    inventario: dict[str, Any] = {}
    ficheros: list[str] = []
    rutas = [args.before, args.after] if comparando else list(args.files)
    leidas: list[Marcas] = []
    for ruta in rutas:
        m = lee(ruta)
        if isinstance(m, str):
            # Un fichero que falta no aborta el resto: se informa y se sigue, y la salida
            # final es 2 porque la herramienta no ha podido mirar todo lo que se le pidió.
            ilegibles.append(str(ruta))
            hallazgos.append(REGLAS["FMT-003"].hallazgo(f"{m}.", fichero=str(ruta)))
            continue
        if m is None:
            hallazgos.append(
                REGLAS["FMT-001"].hallazgo(
                    "Supported: JPEG, PNG, WebP, AVIF/HEIF, MP4/MOV, MP3 and WAV "
                    "(detected by their bytes, not by the extension).",
                    fichero=str(ruta),
                )
            )
            continue
        leidas.append(m)
        inventario[m.fichero] = m.resumen()
        ficheros.append(m.fichero)

    if comparando:
        if len(leidas) == 2:
            hallazgos = compara(leidas[0], leidas[1], jurisdicciones)
        else:
            ilegibles.append("--before/--after")
    else:
        for m in leidas:
            hallazgos += audita(m, jurisdicciones)

    informe = Informe(
        hallazgos=hallazgos,
        ficheros=ficheros or [str(r) for r in rutas],
        jurisdicciones=jurisdicciones,
        modo="compare" if comparando else "audit",
    )
    if args.format == "json":
        print(como_json(informe, inventario))
    elif args.format == "sarif":
        print(como_sarif(informe, __version__))
    else:
        print(texto(informe, color=not args.no_color and sys.stdout.isatty()))

    if ilegibles or not leidas:
        motivo = "some files could not be read" if ilegibles else "no file had a supported format"
        return _error(motivo)
    if informe.errores or (args.strict and informe.avisos):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
