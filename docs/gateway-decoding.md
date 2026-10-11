# Gateway deterministic decoding preregistration

Registered 2026-10-11 before new dev inference or test scoring. Main checked at
`4f5203f`: no MoE boundary/fragment post-processor exists. The referenced
gateway-overredaction-analysis.md is absent there; motivating examples are the
coordinator's A in A4-Papier, hette in etichette, -C in Skłodowskiej-Curie and
ota zgodna in kwota zgodna. These examples are controls, not selection data.

Candidate grid, in tie-break order: `strict`, `inward`, `anchored`.
All use regex WORD Unicode default word boundaries, in Python code-point offsets;
only segments containing a Unicode letter or number are word units. Trim outer
whitespace first. Require at least one fully covered word unit BEFORE snapping.
Strict rejects any partially covered unit; inward clips partial boundary units;
anchored expands partial boundary units only after the whole-unit requirement.
No dictionary, language heuristic, confidence threshold, gold span or test label
is used. Original native detections remain in raw receipts.

Minimum non-whitespace code points: PERSON/ADDRESS/ORG_PARTY/DATE 2, EMAIL 5,
PHONE 7, URL 4, NATIONAL_ID/ACCOUNT_ID/COMPANY_ID/CASE_NUMBER 3, other labels 2.
Checksum-valid national IDs with explicitly supplied country and valid IBANs
bypass minimum length only, never the whole-word requirement. Reuse the country
registry; never infer country from gold, language or digits. Without deployment
country metadata, national-ID checksum status is unknown and does not reject.
Reject invalid national IDs only when an explicit supported country is supplied.
For ACCOUNT_ID matching an IBAN-shaped prefix, require 15–34 ASCII alphanumerics
and mod-97=1 after removing spaces. PHONE permits +, digits, spaces, () . / -
and 7–15 digits. No standalone IBAN/phone validator exists in the core repo;
these are light format checks, not country-specific validity guarantees.

Select ONE rule globally using seed 0 on gateway DEV (eight separate language
configs, 200 conversations each) and TAB dev (126 documents) ONLY. Sources,
licences and hashes are inherited from docs/res100-calibration.md and verified
against its frozen dev gold/comparator receipts; no new source is introduced.
Minimize equal-config macro residual-leak v2 all-subject rate, subject to the
contract v3 paired utility delta CI upper <= .01 against EACH existing dev
comparator (base, kp-280m, TAB-560m, Presidio and separate Shield), EVERY config.
Use 2,000 document/conversation bootstrap resamples, seed 100. Tie break by lower
macro utility, then grid order. If no candidate is feasible, freeze the result
as infeasible and do not select or score test; report the blocked experiment.
No fallback, grid extension or test-based change is permitted.

Persist full dev grid, selected rule, checkpoint/runtime/source hashes and this
protocol hash before test. Seed 1 uses the seed-0 rule unchanged when its transfer
and checksum/training manifests are complete. CPU fp32, four threads, batch 16,
saved 512-token windows, stride 64, simple aggregation/BIOES normalization match
gateway-moe-scoring.md. Atomic raw receipts resume. Existing default seed-0 test
receipts may be replayed with verified hashes and ordered gold; this is a newly
registered decoder evaluation, not retrospective relabelling of the default.

Test scope is all 20 available original configs plus eight gateway configs;
two unpublished Italian/legal configs remain unavailable. OpenPII validation
keeps its name; gateway synthetic test remains dev. Use all six comparators in
gateway-moe-scoring.md, distinct decoded rows, and contract v3 plus v2 reference.
Report cluster/subject n, per-seed Wilson and paired bootstrap 95% CIs, all slices,
RO/PL legacy zero floors, and TAB DIRECT secondary endpoint. Never pool seeds.
Two seeds cannot establish the three-seed contract win; reviewed held-out gold,
disjointness, deployment equivalence, semantic utility and load remain unverified.
