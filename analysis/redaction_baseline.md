# Track C redaction baseline — `ro-realskeleton-v1` (KLU-104)

`config_status=dev` — measurable, code-computed metrics, NOT a citable validated result. Presidio is a **baseline**, not a ranked winner. The post-redaction re-identification leak is computed from **gold offsets** against the redacted text (not a detector re-run), and detection recall is reported **separately** so a high leak is attributable to recall failure (span missed) vs masking policy (span found, partly masked).

| adapter | detection recall | post-redaction leak (95% Wilson CI) | leaked subjects | in-doc bijection | cross-doc bijection | info-retention (proxy) | mask-token ratio |
|---|---:|:--:|---:|---:|---:|---:|---:|
| presidio | 0.442 | 0.009 [0.004, 0.023] | 4/440 | 1.000 | 0.999 | 0.925 | 0.146 |
| dummy | 0.000 | 1.000 [0.991, 1.000] | 440/440 | 1.000 | 1.000 | 1.000 | 0.002 |
