"""Fábrica de fixtures: la CA de prueba y todos los ficheros que la suite necesita.

**En el repositorio no hay ninguna clave privada.** pytest llama a `genera()` una vez
por sesión (ver `conftest.py`), en un directorio temporal: crea allí una CA ECDSA P-256
de usar y tirar con la librería `cryptography`, firma con ella los ficheros C2PA y
construye el resto (XMP, EXIF, chunks PNG/RIFF). Al acabar la sesión el directorio se
borra, y la clave con él.

Sólo están versionados los medios que necesitan ffmpeg (`base/`, `mp3/aigc.mp3`,
`mp4/aigc.mp4`; los regenera `scripts/generar-fixtures.py`) y los pares del estudio S3,
que ya vienen firmados: un fichero firmado no contiene la clave.
"""

from __future__ import annotations

import io
import json
import struct
import wave
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import c2pa
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from PIL import Image

IPTC = "http://cv.iptc.org/newscodes/digitalsourcetype/"
AIGC = {
    "Label": "1",
    "ContentProducer": "001191440300MA5FXTEST0000",
    "ProduceID": "ai-mark-lint-fixture-0001",
    "ReservedCode1": "",
    "ContentPropagator": "",
    "PropagateID": "",
    "ReservedCode2": "",
}
CUANDO = "2026-10-02T10:00:00Z"


# --- CA de prueba ----------------------------------------------------------------------


def credenciales(destino: Path) -> tuple[bytes, bytes]:
    """Crea la CA y el certificado firmante; deja `ca.pem` (público) en `destino`.

    Devuelve (cadena PEM firmante+CA, clave PKCS#8). El perfil es el que exige c2pa-rs:
    hoja con digitalSignature crítica, EKU emailProtection y CA:FALSE.
    """
    ahora = datetime.now(UTC)

    def nombre(cn: str) -> x509.Name:
        return x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, cn),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ai-mark-lint TEST ONLY"),
            ]
        )

    def uso(firma: bool) -> x509.KeyUsage:
        return x509.KeyUsage(
            digital_signature=firma,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=not firma,
            crl_sign=not firma,
            encipher_only=False,
            decipher_only=False,
        )

    clave_ca = ec.generate_private_key(ec.SECP256R1())
    ca = (
        x509.CertificateBuilder()
        .subject_name(nombre("ai-mark-lint TEST root"))
        .issuer_name(nombre("ai-mark-lint TEST root"))
        .public_key(clave_ca.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - timedelta(days=1))
        .not_valid_after(ahora + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(uso(firma=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(clave_ca.public_key()), False)
        .sign(clave_ca, hashes.SHA256())
    )
    clave = ec.generate_private_key(ec.SECP256R1())
    hoja = (
        x509.CertificateBuilder()
        .subject_name(nombre("ai-mark-lint TEST signer"))
        .issuer_name(ca.subject)
        .public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - timedelta(days=1))
        .not_valid_after(ahora + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(uso(firma=True), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(clave.public_key()), False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(clave_ca.public_key()), False
        )
        .sign(clave_ca, hashes.SHA256())
    )
    pem = serialization.Encoding.PEM
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "ca.pem").write_bytes(ca.public_bytes(pem))
    cadena = hoja.public_bytes(pem) + ca.public_bytes(pem)
    pk8 = clave.private_bytes(pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return cadena, pk8


# --- Piezas de metadatos -----------------------------------------------------------------


def xmp(dst: str | None = None, aigc: dict[str, str] | None = None) -> bytes:
    props = f'Iptc4xmpExt:DigitalSourceType="{dst}"' if dst is not None else ""
    hijos = ""
    if aigc is not None:
        valor = json.dumps(aigc, ensure_ascii=False).replace("&", "&amp;").replace("<", "&lt;")
        hijos = f"<TC260:AIGC>{valor}</TC260:AIGC>"
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" '
        'xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" '
        'xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/" '
        'xmlns:TC260="http://www.tc260.org.cn/ns/AIGC/1.0/" '
        f'xmpMM:InstanceID="xmp.iid:ai-mark-lint-0001" {props}>{hijos}'
        '</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    ).encode()


def exif_user_comment(texto: str) -> bytes:
    """TIFF mínimo: IFD0 con el puntero al IFD Exif, y éste con UserComment (ASCII)."""
    valor = b"ASCII\x00\x00\x00" + texto.encode()
    exif_ifd, datos = 8 + 18, 8 + 36
    out = b"II*\x00" + struct.pack("<I", 8)
    out += struct.pack("<H", 1) + struct.pack("<HHII", 0x8769, 4, 1, exif_ifd) + b"\0" * 4
    out += struct.pack("<H", 1) + struct.pack("<HHII", 0x9286, 7, len(valor), datos) + b"\0" * 4
    return out + valor


def jpeg_app1(jpeg: bytes, carga: bytes) -> bytes:
    return jpeg[:2] + b"\xff\xe1" + struct.pack(">H", len(carga) + 2) + carga + jpeg[2:]


def jpeg_con_xmp(jpeg: bytes, paquete: bytes) -> bytes:
    return jpeg_app1(jpeg, b"http://ns.adobe.com/xap/1.0/\x00" + paquete)


def png_chunk(png: bytes, tipo: bytes, datos: bytes) -> bytes:
    chunk = struct.pack(">I", len(datos)) + tipo + datos
    chunk += struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)
    i = png.index(b"IDAT") - 4
    return png[:i] + chunk + png[i:]


def png_itxt_xmp(png: bytes, paquete: bytes) -> bytes:
    return png_chunk(png, b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00" + paquete)


def riff_chunk(riff: bytes, cid: bytes, datos: bytes) -> bytes:
    out = riff + cid + struct.pack("<I", len(datos)) + datos + (b"\0" if len(datos) & 1 else b"")
    return out[:4] + struct.pack("<I", len(out) - 8) + out[8:]


def quita_app11(jpeg: bytes) -> bytes:
    out, i = bytearray(jpeg[:2]), 2
    while i + 4 <= len(jpeg) and jpeg[i] == 0xFF and jpeg[i + 1] not in (0xDA, 0xD9):
        (largo,) = struct.unpack(">H", jpeg[i + 2 : i + 4])
        if jpeg[i + 1] != 0xEB:
            out += jpeg[i : i + 2 + largo]
        i += 2 + largo
    return bytes(out + jpeg[i:])


def _imagen(formato: str, color: tuple[int, int, int], **kw: object) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(b, formato, **kw)
    return b.getvalue()


def _wav() -> bytes:
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(8000)
        w.writeframes(bytes(128 + (i % 16) for i in range(1600)))
    return b.getvalue()


# --- C2PA ------------------------------------------------------------------------------


class Firmante:
    def __init__(self, cadena: bytes, clave: bytes) -> None:
        self._info = c2pa.C2paSignerInfo(
            alg=b"es256", sign_cert=cadena, private_key=clave, ta_url=None
        )

    def firma(
        self,
        origen: bytes,
        mime: str,
        accion: dict[str, object] | None,
        sin_verificar: bool = False,
    ) -> bytes:
        """`sin_verificar` desactiva la validación que c2pa-rs hace tras firmar: hace falta
        para fabricar manifiestos defectuosos a propósito (la librería se niega, con razón,
        a firmar un c2pa.created sin digitalSourceType)."""
        manifiesto: dict[str, object] = {
            "claim_generator_info": [{"name": "ai-mark-lint-fixtures", "version": "0.1.0"}],
            "title": "fixture",
            "assertions": [],
        }
        if accion is not None:
            manifiesto["assertions"] = [{"label": "c2pa.actions", "data": {"actions": [accion]}}]
        ajustes = {"verify": {"verify_after_sign": not sin_verificar}}
        contexto = c2pa.Context(c2pa.Settings.from_dict(ajustes))
        src, dst = io.BytesIO(origen), io.BytesIO()
        with c2pa.Builder(manifiesto, context=contexto) as b:
            b.sign(c2pa.Signer.from_info(self._info), mime, src, dst)
        return dst.getvalue()


def creada(dst: str | None = "trainedAlgorithmicMedia") -> dict[str, object]:
    a: dict[str, object] = {
        "action": "c2pa.created",
        "softwareAgent": {"name": "TestGen Image Model", "version": "3.1"},
        "when": CUANDO,
    }
    if dst is not None:
        a["digitalSourceType"] = IPTC + dst
    return a


# --- El árbol de fixtures ---------------------------------------------------------------


def genera(raiz: Path) -> None:
    """Escribe en `raiz` todas las fixtures propias. `raiz` ya debe contener las
    versionadas (`base/`, `mp3/aigc.mp3`, `mp4/aigc.mp4`)."""
    cadena, clave = credenciales(raiz / "certs")
    f = Firmante(cadena, clave)

    def w(ruta: str, datos: bytes) -> None:
        (raiz / ruta).parent.mkdir(parents=True, exist_ok=True)
        (raiz / ruta).write_bytes(datos)

    ia = IPTC + "trainedAlgorithmicMedia"
    aigc_json = json.dumps(AIGC, ensure_ascii=False)

    # JPEG
    b = io.BytesIO()
    Image.new("RGB", (64, 48), (120, 30, 200)).save(b, "JPEG", quality=90)
    base = b.getvalue()
    c2pa_ia = f.firma(base, "image/jpeg", creada())
    completo = f.firma(jpeg_con_xmp(base, xmp(ia, AIGC)), "image/jpeg", creada())
    w("jpeg/sin-marcas.jpg", base)
    w("jpeg/c2pa-ia.jpg", c2pa_ia)
    w("jpeg/completo.jpg", completo)
    w("jpeg/c2pa-captura.jpg", f.firma(base, "image/jpeg", creada("digitalCapture")))
    w("jpeg/c2pa-sin-dst.jpg", f.firma(base, "image/jpeg", creada(None), sin_verificar=True))
    w(
        "jpeg/c2pa-dst-raro.jpg",
        f.firma(base, "image/jpeg", creada("inventadoPorMi"), sin_verificar=True),
    )
    w("jpeg/iptc-ia.jpg", jpeg_con_xmp(base, xmp(ia)))
    w("jpeg/iptc-codigo-suelto.jpg", jpeg_con_xmp(base, xmp("trainedAlgorithmicMedia")))
    w(
        "jpeg/aigc-exif.jpg",
        jpeg_app1(base, b"Exif\x00\x00" + exif_user_comment(json.dumps({"AIGC": AIGC}))),
    )
    w(
        "jpeg/contradiccion.jpg",
        f.firma(jpeg_con_xmp(base, xmp(ia)), "image/jpeg", creada("digitalCapture")),
    )
    w("jpeg/xmp-roto.jpg", jpeg_con_xmp(base, b"<x:xmpmeta><rdf:RDF><unclosed</x:xmpmeta>"))
    manipulado = bytearray(c2pa_ia)
    manipulado[-20] ^= 0xFF  # contenido cambiado tras firmar
    w("jpeg/c2pa-manipulado.jpg", bytes(manipulado))
    roto = bytearray(c2pa_ia)
    i = roto.find(b"c2pa.signature")
    roto[i + 200 : i + 202] = bytes(x ^ 0xFF for x in roto[i + 200 : i + 202])
    w("jpeg/c2pa-roto.jpg", bytes(roto))
    # Lo que hace un pipeline: re-codificar (pierde todo) y quitar sólo el JUMBF (APP11).
    b = io.BytesIO()
    Image.open(io.BytesIO(completo)).resize((32, 24)).save(b, "JPEG", quality=80)
    w("jpeg/procesado-recodificado.jpg", b.getvalue())
    w("jpeg/procesado-sin-app11.jpg", quita_app11(completo))
    w("jpeg/procesado-sin-aigc.jpg", f.firma(jpeg_con_xmp(base, xmp(ia)), "image/jpeg", creada()))

    # PNG
    png = _imagen("PNG", (10, 120, 60))
    w("png/c2pa-ia.png", f.firma(png, "image/png", creada()))
    w("png/aigc.png", png_chunk(png, b"tEXt", b"AIGC\x00" + json.dumps({"AIGC": AIGC}).encode()))
    w("png/iptc-ia.png", png_itxt_xmp(png, xmp(IPTC + "compositeWithTrainedAlgorithmicMedia")))
    w("png/aigc-json-roto.png", png_chunk(png, b"tEXt", b'AIGC\x00{"Label":"1",'))
    sin_id = {k: v for k, v in AIGC.items() if k != "ProduceID"}
    w("png/aigc-incompleto.png", png_chunk(png, b"tEXt", b"AIGC\x00" + json.dumps(sin_id).encode()))
    raro = {**AIGC, "Label": "7"}
    w("png/aigc-label-raro.png", png_chunk(png, b"tEXt", b"AIGC\x00" + json.dumps(raro).encode()))
    w(
        "png/aigc-dos-distintas.png",
        png_itxt_xmp(
            png_chunk(png, b"tEXt", b"AIGC\x00" + aigc_json.encode()),
            xmp(None, {**AIGC, "ProduceID": "otro-id"}),
        ),
    )

    # WebP
    webp = _imagen("WEBP", (200, 200, 20), lossless=True)
    w("webp/c2pa-ia.webp", f.firma(webp, "image/webp", creada()))
    w("webp/iptc-aigc.webp", _imagen("WEBP", (200, 200, 20), lossless=True, xmp=xmp(ia, AIGC)))

    # WAV
    wav = _wav()
    w("wav/aigc.wav", riff_chunk(wav, b"AIGC", aigc_json.encode()))
    info = b"AIGC" + struct.pack("<I", len(aigc_json)) + aigc_json.encode()
    w("wav/aigc-list-info.wav", riff_chunk(wav, b"LIST", b"INFO" + info))
    w("wav/c2pa-ia.wav", f.firma(wav, "audio/wav", creada()))

    # MP3 y MP4: se firman las bases versionadas (las hizo ffmpeg).
    w(
        "mp3/c2pa-ia.mp3",
        f.firma((raiz / "base/sin-marcas.mp3").read_bytes(), "audio/mpeg", creada()),
    )
    w(
        "mp4/c2pa-ia.mp4",
        f.firma((raiz / "base/sin-marcas.mp4").read_bytes(), "video/mp4", creada()),
    )

    w("otros/no-soportado.txt", b"this is not a media file\n")
