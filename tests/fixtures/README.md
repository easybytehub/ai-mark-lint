# Test fixtures

**No private key is committed — not even a test one.** At the start of every test
session, `tests/conftest.py` copies this folder to a temporary directory and calls
`tests/fabrica.py`, which:

1. creates a throwaway ECDSA P-256 test CA and signer (“ai-mark-lint TEST ONLY”, valid
   30 days) with the `cryptography` library;
2. builds every fixture there: C2PA-signed JPEG/PNG/WebP/WAV/MP3/MP4, XMP with IPTC
   `DigitalSourceType` and `TC260:AIGC`, EXIF `UserComment`, PNG `tEXt`, RIFF chunks,
   and deliberately broken files;
3. deletes the whole directory, key included, when the session ends.

What each fixture must trigger is the `ESPERADO` table in `tests/test_reglas.py`.

Two fixtures are built defective on purpose with c2pa-rs's post-signing verification
turned off, because the library refuses to sign them: `jpeg/c2pa-sin-dst.jpg`
(`c2pa.created` without `digitalSourceType`) and `jpeg/c2pa-dst-raro.jpg`.

## Committed here

- `base/sin-marcas.mp3`, `base/sin-marcas.mp4`: unmarked media, signed at test time.
- `mp3/aigc.mp3`, `mp4/aigc.mp4`: AIGC label written with the exact
  `ffmpeg -metadata AIGC=… -movflags use_metadata_tags` command of the TC260 guides.

These need ffmpeg, so they are committed. Regenerate them with
`.venv/bin/python scripts/generar-fixtures.py`; `--out DIR` also writes the full
generated tree (including the throwaway key) to DIR for inspection — keep DIR outside
the repository.

## `s3/` — copied from the EasyxLab S3 study

Copied unmodified from `easyxlab/studies/s3-ai-marks-survival/fixtures/`
(`img/*-all-remote.*`, `av/mp4-all.mp4` and all of `derived/`) on 2026-10-02. Their
original README is `s3/README-S3.md`. S3 signed them with the c2patool 0.27.22 *test*
certificate; a signed file does not contain the key. The derivatives were produced by
real tools (sharp, ImageMagick, Pillow, ffmpeg, exiftool, next/image). The expected
result for each pair is in `tests/test_s3.py`.
