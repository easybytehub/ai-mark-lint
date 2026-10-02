"""El manifiesto C2PA, leído y validado por la librería oficial (`c2pa-python`).

Aquí no se valida nada a mano: firma, cadena de certificados y hashes los comprueba
`c2pa-rs` por debajo. Este módulo traduce su resultado a un dato estable y separa lo
que la librería mezcla en excepciones: *no hay manifiesto*, *hay uno y no se lee*,
*sólo hay una referencia remota* y *no tengo la librería*.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Usos extendidos de clave (EKU) que se aceptan en el certificado del firmante: la lista por
# defecto de c2pa-rs (`sdk/src/crypto/cose/valid_eku_oids.cfg`, v0.91.0). c2pa-rs la trae, pero
# un contexto creado desde `Settings` sin `trust_config` se comporta como si estuviera vacía y
# rechaza con `signingCredential.invalid` los certificados C2PA normales (los de OpenAI
# emitidos por Trufo, los de Microsoft…). Lo midió el estudio S6 de EasyxLab en Wikimedia
# Commons: 187 manifiestos válidos dados por inválidos en ai-mark-lint 0.1.0.
EKU_POR_DEFECTO = """\
// id-kp-emailProtection
1.3.6.1.5.5.7.3.4

// id-kp-documentSigning
1.3.6.1.5.5.7.3.36

// id-kp-timeStamping
1.3.6.1.5.5.7.3.8

// id-kp-OCSPSigning
1.3.6.1.5.5.7.3.9

// MS C2PA Signing
1.3.6.1.4.1.311.76.59.1.9

// C2PA Signing
1.3.6.1.4.1.62558.2.1
"""


class AnclasInvalidas(ValueError):
    """El PEM de --trust-anchors no se puede usar. Es un error de uso (salida 2)."""


@dataclass(frozen=True)
class C2paInfo:
    estado: str
    """`ausente`, `solo_referencia`, `sin_libreria`, `ilegible`, `invalido`, `valido`
    o `confiable`. `solo_referencia` es un fichero sin manifiesto incrustado que apunta
    a uno remoto: no es una marca, es un enlace."""
    error: str = ""
    fallos: tuple[str, ...] = ()
    fallos_cawg: tuple[str, ...] = ()
    no_confiable: bool = False
    caducidad_por_tsa: bool = False
    """El certificado caducó y su validez al firmar depende de una TSA no confiable."""
    actualizacion: bool = False
    etiqueta: str = ""
    version_claim: int | None = None
    hay_acciones: bool = False
    primera_accion: dict[str, Any] = field(default_factory=dict)
    tipos_fuente: tuple[str, ...] = ()
    tipos_fuente_ingredientes: tuple[str, ...] = ()
    agentes: tuple[tuple[str, str], ...] = ()
    cuando: tuple[str, ...] = ()
    firmante: str = ""
    hora_firma: str = ""
    generador: tuple[tuple[str, str], ...] = ()

    @property
    def estado_en(self) -> str:
        return {
            "ausente": "absent",
            "solo_referencia": "remote reference only",
            "sin_libreria": "c2pa-python missing",
            "ilegible": "unreadable",
            "invalido": "invalid",
            "valido": "valid",
            "confiable": "trusted",
        }[self.estado]

    @property
    def legible(self) -> bool:
        return self.estado in ("invalido", "valido", "confiable")

    @property
    def firma_valida(self) -> bool:
        return self.estado in ("valido", "confiable")


def _nombre_version(obj: Any) -> tuple[str, str]:
    if isinstance(obj, dict):
        return str(obj.get("name", "") or ""), str(obj.get("version", "") or "")
    if isinstance(obj, str):
        return obj, ""
    return "", ""


def _acciones(manifiesto: dict[str, Any]) -> list[list[dict[str, Any]]]:
    return [
        list((a.get("data") or {}).get("actions", []))
        for a in manifiesto.get("assertions", [])
        if str(a.get("label", "")).startswith("c2pa.actions")
    ]


def clasifica(codigos: list[str]) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    """(no confiable, fallos del núcleo C2PA, fallos CAWG).

    Todo código `*.untrusted` (firmante, sello de tiempo, credencial CAWG) es cuestión de
    qué lista de confianza aplica el verificador, no un defecto del fichero. Los `cawg.*`
    son de la aserción de identidad de la Creator Assertions Working Group, que no es el
    núcleo de la especificación C2PA: se informan aparte y nunca invalidan el manifiesto.
    """
    no_confiable = any(c.endswith(".untrusted") for c in codigos)
    resto = [c for c in codigos if c and not c.endswith(".untrusted")]
    cawg = tuple(c for c in resto if c.startswith("cawg."))
    nucleo = tuple(c for c in resto if not c.startswith("cawg."))
    return no_confiable, nucleo, cawg


def interpreta(
    datos: dict[str, Any], estado_libreria: str, detallado: dict[str, Any] | None = None
) -> C2paInfo:
    """Del JSON del Reader a `C2paInfo`. Separado de `lee` para poder probarlo sin
    ficheros (un sello de tiempo, por ejemplo, no se puede fabricar sin una TSA)."""
    etiqueta = str(datos.get("active_manifest", ""))
    manifiesto = (datos.get("manifests") or {}).get(etiqueta, {})

    resultados = (datos.get("validation_results") or {}).get("activeManifest") or {}
    codigos = [str(v.get("code", "")) for v in resultados.get("failure", [])] or [
        str(v.get("code", "")) for v in datos.get("validation_status", [])
    ]
    no_confiable, fallos, cawg = clasifica(codigos)

    # Con un sello de tiempo íntegro de una TSA que no está en la lista de confianza,
    # c2pa-rs ignora la hora del sello y comprueba el certificado a fecha de hoy: si ya
    # caducó, sale `signingCredential.expired`. Eso depende de confiar en la TSA, no del
    # fichero. Sin sello de tiempo, en cambio, la caducidad es un fallo real.
    informativos = {str(v.get("code", "")) for v in resultados.get("informational", [])}
    caducidad_por_tsa = (
        "timeStamp.untrusted" in informativos and "signingCredential.expired" in fallos
    )
    if caducidad_por_tsa:
        fallos = tuple(c for c in fallos if c != "signingCredential.expired")
        no_confiable = True

    grupos = _acciones(manifiesto)
    acciones = grupos[0] if grupos else []  # § 18.14.2 mira la primera aserción
    todas = [a for g in grupos for a in g]

    # Editar un contenido generado produce un manifiesto nuevo que empieza con
    # c2pa.opened y lleva el original como ingrediente: la declaración de IA vive en el
    # manifiesto del ingrediente, y es C2PA correcto.
    ingredientes = [
        str(a["digitalSourceType"])
        for nombre, otro in (datos.get("manifests") or {}).items()
        if nombre != etiqueta
        for g in _acciones(otro)
        for a in g
        if a.get("digitalSourceType")
    ]

    # Un Update Manifest no lleva hard binding (c2pa.hash.*) y § 18.14.2 no se le aplica
    # («This requirement does not apply to Update Manifests»). El JSON simple oculta las
    # aserciones de hash; el detallado las lista.
    actualizacion = False
    if detallado is not None:
        activo = (detallado.get("manifests") or {}).get(detallado.get("active_manifest"), {})
        etiquetas = list((activo.get("assertion_store") or {}).keys())
        actualizacion = bool(etiquetas) and not any(e.startswith("c2pa.hash.") for e in etiquetas)

    firma = manifiesto.get("signature_info") or {}
    generador = [_nombre_version(g) for g in manifiesto.get("claim_generator_info", [])]
    if not generador and manifiesto.get("claim_generator"):
        generador = [_nombre_version(manifiesto["claim_generator"])]

    if fallos or (estado_libreria == "Invalid" and not codigos):
        estado = "invalido"
    elif estado_libreria == "Trusted":
        estado = "confiable"
    else:
        # «Invalid» sólo por códigos *.untrusted o cawg.* sigue siendo una firma íntegra.
        estado = "valido"

    return C2paInfo(
        estado=estado,
        fallos=fallos,
        fallos_cawg=cawg,
        no_confiable=no_confiable,
        caducidad_por_tsa=caducidad_por_tsa,
        actualizacion=actualizacion,
        etiqueta=etiqueta,
        version_claim=manifiesto.get("claim_version"),
        hay_acciones=bool(grupos),
        primera_accion=acciones[0] if acciones else {},
        tipos_fuente=tuple(
            str(a["digitalSourceType"]) for a in todas if a.get("digitalSourceType")
        ),
        tipos_fuente_ingredientes=tuple(ingredientes),
        agentes=tuple(
            _nombre_version(a.get("softwareAgent")) for a in todas if a.get("softwareAgent")
        ),
        cuando=tuple(str(a["when"]) for a in todas if a.get("when")),
        firmante=str(firma.get("issuer") or firma.get("common_name") or ""),
        hora_firma=str(firma.get("time") or ""),
        generador=tuple(generador),
    )


def contexto(anclas: str | None) -> Any:
    """El contexto de la librería. **Nunca se va a la red**: un fichero puede apuntar a
    un manifiesto remoto, y seguirlo convertiría un linter de CI en un cliente HTTP
    dirigido por el fichero que audita. Lanza `AnclasInvalidas` si el PEM no sirve."""
    import c2pa

    if anclas is not None:
        if "-----BEGIN CERTIFICATE-----" not in anclas:
            raise AnclasInvalidas("no PEM certificate found")
        try:  # cryptography llega con c2pa-python; c2pa-rs acepta un PEM roto en silencio
            from cryptography import x509
        except ImportError:  # pragma: no cover
            pass
        else:
            try:
                x509.load_pem_x509_certificates(anclas.encode())
            except ValueError as exc:
                raise AnclasInvalidas(f"unreadable certificate: {exc}") from exc
    ajustes: dict[str, Any] = {
        "verify": {"remote_manifest_fetch": False},
        "trust": {"trust_config": EKU_POR_DEFECTO},
    }
    if anclas is not None:
        ajustes["verify"]["verify_trust"] = True
        ajustes["trust"]["trust_anchors"] = anclas
    try:
        return c2pa.Context(c2pa.Settings.from_dict(ajustes))
    except c2pa.C2paError as exc:
        raise AnclasInvalidas(str(exc)) from exc


def lee(ruta: Path, rastro: bool, anclas: str | None = None) -> C2paInfo:
    try:
        import c2pa
    except (ImportError, OSError):  # OSError: la librería nativa no carga
        return C2paInfo(estado="sin_libreria" if rastro else "ausente")

    ctx = contexto(anclas)
    try:
        lector = c2pa.Reader(str(ruta), context=ctx)
    except c2pa.C2paError.ManifestNotFound:
        if rastro:
            # Hay firma JUMBF de C2PA y la librería no encuentra manifiesto: está roto.
            return C2paInfo(estado="ilegible", error="C2PA JUMBF data present but unreadable")
        return C2paInfo(estado="ausente")
    except c2pa.C2paError as exc:
        mensaje = f"{type(exc).__name__.lstrip('_')}: {exc}"
        if anclas is not None and isinstance(exc, c2pa.C2paError.Signature) and not rastro:
            raise AnclasInvalidas(str(exc)) from exc
        if not rastro and (
            "remote" in str(exc).lower() or isinstance(exc, c2pa.C2paError.RemoteManifest)
        ):
            return C2paInfo(estado="solo_referencia", error=str(exc))
        if not rastro:
            # Sin firma JUMBF no hay manifiesto: lo que falló es el contenedor.
            return C2paInfo(estado="ausente", error=mensaje)
        return C2paInfo(estado="ilegible", error=mensaje)

    try:
        datos = json.loads(lector.json())
        detallado = json.loads(lector.detailed_json())
        estado = str(lector.get_validation_state() or "")
    finally:
        lector.close()
    return interpreta(datos, estado, detallado)
