# Public fixtures from c2pa-rs

Copied unmodified from `sdk/tests/fixtures/` of
[contentauth/c2pa-rs](https://github.com/contentauth/c2pa-rs) (licence: MIT OR
Apache-2.0). On 2026-10-02 each file's git blob hash matched the one on the default
branch:

| file | blob sha | why it is here |
|---|---|---|
| `C.jpg` | b6579b3281fbd448163f77fe46bf8d24f3e5a018 | valid manifest; “before” of the orphan-XMP pair |
| `no_manifest.jpg` | e455cdac7b1580d90a4a42a602a0ade69c9da89a | XMP `dcterms:provenance="self#jumbf=/c2pa/…"` with no JUMBF: not a manifest |
| `C_with_CAWG_data.jpg` | dd93c44d7b4429fbc0dcc8713df1bb7f563a3375 | `cawg.x509.credential.untrusted`: a trust code, not an invalid manifest |
| `update_manifest.jpg` | 0e81a6cdae5828b3887d36e2930aca9f1a9103e4 | Update Manifest: § 18.14.2 does not apply |

They reproduce false positives found in an adversarial review of v0.1.0.
