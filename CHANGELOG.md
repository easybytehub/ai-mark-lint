# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: SemVer.

## [0.1.0] — unreleased

First release.

### Added
- `ai-mark-lint` CLI with text, JSON and SARIF output. Options: `--jurisdiction
  eu,ca,cn|none` (default `eu,ca`), `--format text|json|sarif`, `--strict`,
  `--before A --after B`, `--trust-anchors PEM`, `--no-color`.
- Exit codes: `0` no errors, `1` errors (or warnings with `--strict`), `2` the tool could
  not do its job. Unreadable files are reported (FMT-003) without stopping the others;
  invalid trust anchors and internal errors exit `2` with a one-line message, never a
  traceback.
- Pure-Python reading of JPEG, PNG, WebP, AVIF/HEIF, MP4/MOV, MP3 and WAV (XMP, EXIF
  UserComment, PNG/RIFF chunks, ID3v2 TXXX, `moov.udta.meta`), hardened against hostile
  files (nested RIFF lists, truncated ID3 headers, impossible box sizes).
- C2PA validation with `c2pa-python` 0.38 (c2pa-rs 0.91), offline. A manifest is
  detected by the JUMBF `jumd` box with the C2PA UUID, not by loose substrings. Trust
  codes (`*.untrusted`) are undetermined, never errors; CAWG identity codes are reported
  apart; Update Manifests are exempt from § 18.14.2.
- 35 rules: technical (C2PA, IPTC, XMP, container), EU (Art. 50(2), Art. 111(4) and the
  Code of Practice), California (§ 22757.3(b)), China (CAC Measures, GB 45438-2025, TC260
  guides) and before/after comparison. A rule not verified at its source is never an
  error; three are tagged `[unverified]`.
- Compare mode `--before A --after B`: which marks a pipeline removes or breaks; losing
  the IPTC AI declaration is an error, changing it is a warning.
- `SPEC.md` with the literal sentence, URL and access date of every rule.
- GitHub Action (composite, installs from its own code), CI workflow and release
  workflow (build, provenance attestation, GitHub Release, PyPI via Trusted Publishing
  once enabled). Every third-party action pinned by SHA with its exact version.
- Tests: fixtures built at test time with a throwaway CA (no private key in the
  repository), 13 before/after pairs from the EasyByte Lab S3 study and four public
  c2pa-rs fixtures that reproduce the false positives of an adversarial review.
