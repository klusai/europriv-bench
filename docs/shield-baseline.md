# kOS Shield HTTP baseline (RES-122)

`--adapter shield` calls the kOS Shield service's `/anonymize-batch`. It is a
separate board entry from `--adapter presidio`, which still runs stock Presidio
locally with its English recognizers and threshold 0.0. No Shield recognizers
are copied into this repository or implemented in the adapter.

The reviewed source is `klusai-webos`, commit
`8f4c04cd29f04d3bfe826c5396aa6c5343159058`, under `services/presidio/`;
the application client is `klusai_webos/privacy/presidio/remote.py`.
Shield's threshold is 0.8, its replace policy is `DEFAULT: replace`, and its
postprocessing trims whitespace, merges overlapping entities, restricts address
extension to house numbers, and splits long stretches between words.

## Pin and run

Start a dedicated local service from the mirror following its README. Do not
point evaluation at the shared application service. Complete its normal readiness
canary; the benchmark attestation also requires the model artifact/revision and
single-process lock settings described in the service README.

```bash
python -m europriv_bench.shield --url http://127.0.0.1:11439 --out /scratch/shield-pin.json
export EUROPRIV_SHIELD_URL=http://127.0.0.1:11439
export EUROPRIV_SHIELD_PIN=/scratch/shield-pin.json
# Review the pin before scoring. The capture command refuses to overwrite it.
mkdir -p /scratch/shield-suite
cp evaluations/pii-detection-en.yaml /scratch/shield-suite/
europriv run --adapter shield --suite /scratch/shield-suite --out /scratch/shield.json
```

The pin contains both language inventories, the webos commit and source digest,
requirements digest, installed dependency versions, model artifact hashes,
threshold, operators, postprocessing and device. Capture checks that the service's
recognizer fingerprint actually hashes the declared operators and postprocessing;
a different policy requires an explicit adapter update, not a silently new label.
Inference checks the pin before and after each call and the fingerprint and attested
process identity on every batch. The benchmark request header also enables the
service's single-process enforcement. Failure, restart or drift aborts the
evaluation. A pin is evidence from the configured service, not independent
verification of a remote deployment.

Every row contains `service_provenance` with the active language configuration,
requested/resolved language, request policy, mapping and full pin digest. The
board's `model_id` includes that digest, so different service pins cannot overwrite
one another or stock Presidio. No credentials or base URL enter the row.
The pin digest hashes canonical JSON (sorted keys, compact separators), not file whitespace.
The recorded local run uses [this pin](../baselines/shield-service-pin.json).

## Language and offset semantics

The runner passes each spec's language to Shield. The exact service supports
English and Dutch; RO, PL, DE, ES, FR and IT resolve to Dutch. This fallback is
reported explicitly; these rows do not claim native recognizers for those languages.

Texts remain independent batch elements in request order. The adapter sends whole
documents, with no application-side 16k splitting or accelerator routing. Shield
owns internal splitting and returns Python character offsets into each original
input. Bounds and returned surface strings must agree before the shared KP
whitespace-token alignment runs. Redacted-output offsets, byte offsets, missing
results, reordered/duplicate indexes and failed items are never scored as success.
There is no fallback to stock Presidio or to all-O tags.

Shield adds ORGANIZATION → ORG_PARTY, NL_POSTAL_CODE → ADDRESS, NL_BSN and
ID_DOCUMENT → NATIONAL_ID, and NL_CADASTRAL_PARCEL → ADDRESS to the stock mapping.
ABBREVIATION, NRP and other types with no clean KP equivalent are dropped;
the runner still applies its common gold-label fairness mask. `anonymize` returns
the service's text, preserving its actual operators; pseudonymization is not
implemented for this fixed replace-policy baseline.

## Resumable requested suite

Install `pyarrow` for this analysis script (not needed by the HTTP adapter):

```bash
python analysis/score_shield_leaderboard.py --scratch /scratch/res122 \
  --revision 58faa4fa572cd8064818a6e1f8ca6e361b959c00
```

The script downloads the existing licensed benchmark parquet files with
`hf_hub_download`, checkpoints each 16-document prediction batch, and writes a
completed harness row per config: TAB, RO/PL real-skeleton and EN/DE/ES/FR/IT/NL.
Resume requires the same service pin, dataset revision and parquet content digest.
Point estimates come from `run_spec`; F1/F2 have 2,000 document-bootstrap resamples
(seed 122), and leakage retains the harness Wilson intervals and denominators.
One inference run is not a multi-seed result. No superiority claim is established
by merely adding these rows. General-config contamination remains `unknown`
until Shield's complete model training provenance is audited.
