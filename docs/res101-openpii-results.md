# RES-101 — published OpenPII evaluation

Main `14cfc44` could not load any of the ten OpenPII configs: they were not published in
`klusai/europriv-bench`. The repaired YAMLs point to Ai4Privacy `default` / `validation`
with pinned parquet files; language-specific `eval_config` identities preserve contamination policy.

The first 400 source candidates per language yield 3,985 documents after 15 counted token-collision
exclusions, without replacement. Source substring equality and strict BIOES are validated.
[Source, licence, revision and checksums](ai4privacy-openpii-manifest.yaml). Config status remains `dev`.

Entity F1, harness `run_spec`, with 95% document-bootstrap percentile CIs (2,000 resamples, seed 122).
One inference seed (101), one fixed checkpoint per model; training seed count was not verified.

| Language | n | KP-280m F1 [95% CI] | 560m-legal F1 [95% CI] | Presidio F1 [95% CI] |
|---|---:|---:|---:|---:|
| cs | 399 | 0.428 [0.411, 0.446] | 0.345 [0.325, 0.365] | 0.279 [0.264, 0.293] |
| de | 399 | 0.301 [0.284, 0.319] | 0.309 [0.293, 0.326] | 0.241 [0.228, 0.255] |
| el | 397 | 0.344 [0.327, 0.362] | 0.291 [0.272, 0.311] | 0.338 [0.323, 0.353] |
| fi | 399 | 0.367 [0.352, 0.383] | 0.284 [0.268, 0.303] | 0.285 [0.271, 0.300] |
| fr | 398 | 0.349 [0.332, 0.367] | 0.334 [0.315, 0.355] | 0.343 [0.326, 0.361] |
| hu | 400 | 0.297 [0.282, 0.313] | 0.305 [0.289, 0.321] | 0.296 [0.282, 0.309] |
| nl | 399 | 0.345 [0.328, 0.363] | 0.313 [0.295, 0.332] | 0.292 [0.278, 0.306] |
| pl | 397 | 0.340 [0.322, 0.359] | 0.313 [0.295, 0.331] | 0.262 [0.248, 0.277] |
| ro | 400 | 0.346 [0.330, 0.362] | 0.324 [0.307, 0.341] | 0.303 [0.289, 0.317] |
| sv | 397 | 0.372 [0.355, 0.390] | 0.299 [0.281, 0.317] | 0.265 [0.251, 0.278] |

Both KP models: `clean_held_out` on nine languages, `unknown` on Romanian under existing harness policy.
Presidio: `clean_held_out` throughout; default English NER is used across languages.
OpenMed and TabularisAI: `in_distribution` throughout because Ai4Privacy is a training substrate;
they were not rescored in this task. These labels do not prove absence of row-level training overlap.

KP-280m revision: `bc977796e2002e8ab045664618ed8372781896bd`.
560m-legal revision: `af6635cb3db84c88da91aae71289227240d81912`.
KP inference: local MPS, fp32, batch 16; Presidio: local CPU. F2 and its CIs, package versions,
gold hashes, excluded UIDs and full dataset provenance are in `baselines/leaderboard.json`.
The 30 rows were spliced into that board with existing entries and ordering preserved.

Reproduce (Python 3.13 with `hf`, `presidio`, `dev` extras and `en_core_web_lg` installed):

```sh
PYTHONPATH=src PYTORCH_ENABLE_MPS_FALLBACK=1 TOKENIZERS_PARALLELISM=false python analysis/score_openpii.py --scratch /path/to/res101 --device mps
make check
```

Predictions checkpoint after every batch; rerunning with the same scratch resumes and checks source/model identity.
No multi-seed training comparison, exhaustive train/eval deduplication, real-gold result, or new win claim.
The historical 80-row analysis files use older local slices and are not paired comparisons to this run.
