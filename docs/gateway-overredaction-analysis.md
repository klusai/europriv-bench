# Gateway-trained MoE seed 0: DEV over-redaction analysis

2026-10-11. **All 5,759 over-redacted fragments in all 1,600 DEV conversations were
classified: (a) 0 confirmed gold gaps, (b) 4,899 hard-negative confusions,
(c) 8 boundary extensions, (d) 852 other false positives.** The strongest next step
is training on independently generated merchant/product and ordinary-status negatives.
This audit does not justify expanding protected gold to make the model look better.
Polish DEV utility loss is 11.23% [8.23%, 13.95%], with receipt-status text adding a
large component beyond the merchant-name errors shared across languages.

## Scope, provenance and units

`origin/main` was fetched first at `2ce13cf0c698a7a1ff0b344052e008e671dc13f5`;
this document did not exist. Fresh, offline CPU inference used only
`/Users/mihai/codespace/research-worktrees/res124/artifacts/gateway-traffic-v1/dev.jsonl`:
200 conversations per language, eight reserved scenario families per language.
Neither test data nor test predictions were opened. The numbers in the task prompt
are context, not reproduced DEV results or evidence used to adjudicate spans.

Checkpoint: `/Users/mihai/codespace/research-artifacts/gateway/seed0/merged`.
All four model/tokenizer files matched `seed0/gw0.sha256`; weights SHA-256:
`0e844ccb9e6469b85631e44d20bea5743d1176beaf3667e924b2fe33f471d0ea`.
DEV SHA-256: `eb59f81485860c100682253471bbba218a648ccb4f6926666bab3c29dfc4e751`.
Manifest SHA-256: `15012ebb23289000af8acaca03bb505ded43378db1420924a1c6c60801061663`.
Guide SHA-256: `e71e2da9a35bd8fe03effb9a54d088bb45226dee4d687b1ec4b1232828b1e0dc`.
The existing manifest identifies these original synthetic conversations as CC-BY-4.0,
KlusAI / Codex, source <https://github.com/klusai/klusai-datasets>, with training and
redistribution permitted. No new source was introduced.

Python 3.13.12, torch 2.12.0, transformers 5.10.2; CPU fp32, four threads, batch 16,
512-token overflow windows, stride 64, simple aggregation, all native labels,
no confidence threshold. `Res100MoEAdapter` is supplied an explicit 512-token pipeline
matching `analysis/score_gateway_moe.py` at main `4f5203f`; its receipt method supplies
exact character intervals. BIOES normalization does not expand their coverage.
**One training seed (0), one final 512-token inference pass (RNG 100); no training
or comparator run.** A preliminary pass using the legacy adapter's forced 256-token
window was excluded after the required main sync supplied the gateway scoring code.
The final setting matches the existing gateway protocol; it was not selected by score.

An error fragment is a connected component of the union of removed intervals minus
the union of protected gold, trimming exterior whitespace and excluding whitespace-only
components. Each Unicode non-whitespace character is counted once. A raw prediction
can yield multiple fragments; fragmented predictions need not be whole words.
`gateway_utility` and `utility_counts` in the harness score the unchanged gold.
For every language, the classified character sum equals the harness's entire
removed-non-PII numerator, with no exclusions or unclassified residual.

The single Codex multilingual review used all error-bearing field/line contexts,
grouping identical CSV cells and repeated lines (468 groups). It inspected the exact
removed pieces, native labels and gold overlap; grouping did not sample away errors.
The [per-fragment ledger](validation/gateway-overredaction-ledger.tsv) records all IDs,
flat-text offsets, class, reason, character count, review group and context hash.
This is an AI contextual adjudication, **not independent native-human validation**.

Classes are mutually exclusive:

- **(a) Gold gap:** actual personal data required by the frozen guide but missing gold.
- **(b) Hard-negative confusion:** example merchants, product descriptions/codes,
  public figures, public legal dates/references, or ordinary numeric fields.
- **(c) Boundary spillover:** excess text in a removed component whose contributing
  raw prediction overlaps protected gold, after excluding a genuine gold gap.
- **(d) Other:** ordinary instructions/status prose or CSV headers, including their
  subword fragments. Subword chopping of a false positive alone is not evidence of
  expansion beyond gold. Mixed currency/status fragments receive their status cause.

## Counts and uncertainty

Each class cell is **count; percentage of that language's error fragments [95% Wilson CI]**.
These intervals describe the fixed single-review labels; they do not quantify reviewer
error. Repeated CSV cells are correlated, so fragment Wilson intervals are descriptive,
not independent-observation evidence of a model win.

| Language | Error fragments n | (a) Gold gap | (b) Hard negative | (c) Boundary | (d) Other |
|---|---:|---|---|---|---|
| PL | 1,582 | 0; 0.00% [0.00, 0.24] | 1061; 67.07% [64.71, 69.34] | 0; 0.00% [0.00, 0.24] | 521; 32.93% [30.66, 35.29] |
| DE | 742 | 0; 0.00% [0.00, 0.52] | 670; 90.30% [87.95, 92.22] | 4; 0.54% [0.21, 1.38] | 68; 9.16% [7.29, 11.46] |
| NL | 751 | 0; 0.00% [0.00, 0.51] | 715; 95.21% [93.44, 96.52] | 0; 0.00% [0.00, 0.51] | 36; 4.79% [3.48, 6.56] |
| IT | 525 | 0; 0.00% [0.00, 0.73] | 497; 94.67% [92.40, 96.28] | 2; 0.38% [0.10, 1.38] | 26; 4.95% [3.40, 7.16] |
| EN | 362 | 0; 0.00% [0.00, 1.05] | 359; 99.17% [97.59, 99.72] | 0; 0.00% [0.00, 1.05] | 3; 0.83% [0.28, 2.41] |
| RO | 885 | 0; 0.00% [0.00, 0.43] | 732; 82.71% [80.08, 85.06] | 0; 0.00% [0.00, 0.43] | 153; 17.29% [14.94, 19.92] |
| FR | 369 | 0; 0.00% [0.00, 1.03] | 344; 93.22% [90.19, 95.37] | 1; 0.27% [0.05, 1.52] | 24; 6.50% [4.41, 9.50] |
| ES | 543 | 0; 0.00% [0.00, 0.70] | 521; 95.95% [93.94, 97.31] | 1; 0.18% [0.03, 1.04] | 21; 3.87% [2.54, 5.84] |

Utility is removed gold-non-PII, non-whitespace characters / all gold-non-PII,
non-whitespace characters. Intervals below use the harness conversation-cluster
percentile bootstrap: **2,000 resamples, RNG 126, all 200 conversations per language**,
including zero-error conversations. Each draw resamples whole conversations and takes
a ratio of sums. Class contributions use the same denominator and bootstrap draws.
These are absolute rate intervals against a zero reference, not comparator deltas.
They are conditional on these eight synthetic families; shared templates/translations
limit generalization beyond this DEV corpus. No pooled cross-language CI is claimed.

| Language | Conversations with error / 200 | Removed / eligible characters | Utility loss %, 95% cluster CI |
|---|---:|---:|---:|
| PL | 92 / 200 | 11,624 / 103,530 | 11.23 [8.23, 13.95] |
| DE | 53 / 200 | 3,884 / 113,713 | 3.42 [2.40, 4.38] |
| NL | 53 / 200 | 3,910 / 106,448 | 3.67 [2.61, 4.71] |
| IT | 52 / 200 | 2,561 / 109,011 | 2.35 [1.66, 3.02] |
| EN | 33 / 200 | 1,363 / 115,434 | 1.18 [0.77, 1.62] |
| RO | 53 / 200 | 4,793 / 106,151 | 4.52 [3.10, 5.87] |
| FR | 35 / 200 | 1,368 / 109,001 | 1.26 [0.83, 1.69] |
| ES | 35 / 200 | 2,498 / 108,534 | 2.30 [1.53, 3.06] |

Contribution to utility loss in **percentage points [95% cluster CI]**:

| Language | (b) Hard negative | (c) Boundary | (d) Other |
|---|---:|---:|---:|
| PL | 6.235 [4.327, 7.994] | 0.000 [0.000, 0.000] | 4.993 [3.862, 6.034] |
| DE | 3.044 [2.041, 3.981] | 0.035 [0.001, 0.082] | 0.337 [0.226, 0.458] |
| NL | 3.432 [2.321, 4.496] | 0.000 [0.000, 0.000] | 0.241 [0.148, 0.358] |
| IT | 2.113 [1.406, 2.778] | 0.033 [0.000, 0.088] | 0.204 [0.115, 0.310] |
| EN | 1.145 [0.732, 1.586] | 0.000 [0.000, 0.000] | 0.036 [0.000, 0.091] |
| RO | 3.572 [2.468, 4.641] | 0.000 [0.000, 0.000] | 0.943 [0.582, 1.329] |
| FR | 1.094 [0.701, 1.506] | 0.014 [0.000, 0.048] | 0.148 [0.083, 0.224] |
| ES | 2.139 [1.394, 2.857] | 0.021 [0.000, 0.070] | 0.142 [0.072, 0.226] |

Class (a) contributes zero observed characters in every language. Its all-zero bootstrap
is degenerate, not proof that unseen gold gaps are impossible; the Wilson upper bounds
above and the missing independent review must remain visible. The same qualification
applies to languages with zero observed class (c).

## Contextual findings and examples

Offsets below are `[start,end)` in the harness's flattened conversation; full IDs start
`gateway-v1/dev/`. Only illustrative snippets are quoted; raw receipts stay in scratch.
**No confirmed class-(a) example was found**, including in PL/DE/NL/IT. The following
suspected-gap checks explain why superficially entity-like text was not relabelled:

| Language / DEV location | Observed text and judgment |
|---|---|
| PL `02-001:32:34` | `-C` inside *Marii Skłodowskiej-Curie*: the inflected name refers to the public historical figure in a science quiz. The guide explicitly retains public historical figures: (b), not a missing PERSON label. |
| PL `01-000:779:789` | `ota zgodna` inside `kwota zgodna` (“amount matches”): receipt reconciliation status, not a person's name, account number, or health condition: (d). `inna nazwa sklepu` means “different shop name”; `nazwa skrócona` means “abbreviated name” and describes merchant reconciliation, not an unannotated customer name. |
| DE `01-000:726:727` | `A` inside `A4-Papier`: a paper product in the Artikel column, not an address or identifier: (b). `Buchungstext` is a column heading (“transaction description”), not a missing personal value: (d). |
| NL `01-000:665:666` | `A` inside `A4-papier`: the same product confusion in Dutch: (b). `apparaat toegewezen` (“device assigned”) and `groep wil samenblijven` (“group wants to stay together”) are task statuses; they supply no missing personal identifier under this guide: (d). |
| IT `01-001:730:735` | `hette` inside `rotolo di etichette` (“roll of labels”): a product, not a person's name: (b). `etichetta mancante` means a missing return label, not a missing gold privacy label. |
| All languages, public-law negatives | `2018-05-25`, `2016/679`, and `32016R0679` occur in a public regulation/source-citation context. These are deliberately retained public dates/statute references: (b). No observed excess fragment exposed an unlabelled DOB or personal address. |

Generic appointment notes such as Polish `nowa godzina telefonicznie` (“new time
communicated by phone”) contain neither the actual time nor a telephone number.
`dwie wizyty w portalu` describes a scheduling inconsistency, not an omitted diagnosis.
Existing DOB/address/diagnosis fields remain protected as authored. A broader policy
for protecting all facts associated with a person would require explicit policy review;
it is not a reason to silently mark these fragments as current-gold errors.

All languages have merchant-alias confusions in expense CSVs, commonly `DESK STORE`,
`PAPER SHOP`, `PAPER-SHOP EU`, `TECH CORNER`, and `OFFICE DIRECT WEB`. These are example
merchant labels explicitly retained by the guide; predicted PERSON/ORG_PARTY labels
cannot establish a gold gap. Polish has 840 merchant fragments (4,813 characters),
209 CSV-product fragments plus one public-table product fragment (1,588 characters),
and 4,175 characters of receipt-status errors. The latter includes pieces extending
across `EUR;` or a CSV separator into `nazwa skrócona`; neither adjacent gold nor a
missing account value explains them. Polish also has 994 ordinary-prose/status
characters outside that receipt-status bucket. The category-(d) total is 5,169.

Expense family `gateway-v1/family-004` accounts for most removed characters in every
language. For PL it contributes 10,576 / 11,624; for DE 3,498 / 3,884; NL 3,573 / 3,910;
IT 2,239 / 2,561; EN 1,220 / 1,363. Counts are descriptive corpus attribution, not
independent replicates of a failure mechanism. The machine-readable summary includes
all eight family breakdowns and the complete class statistics.

The eight confirmed (c) fragments remove only 114 non-whitespace characters total:
DE 4/40, FR 1/15, ES 1/23, IT 2/36 (fragments/characters). For example:

- DE `02-007:673:695`: `Anna Meyer` is gold; the PERSON prediction continues through
  `— Tabellen; Referenzen` (“spreadsheets; references”). This is an actual span extension.
- IT `00-004:166:186`: the PERSON span for `Sara Romano` continues into
  `— etichetta mancante`. A second instance occurs at `00-016:165:185` after `Maria Rossi`.
- FR `03-001:611:628`: the PERSON prediction continues from `Emma Richard` into
  `— courriel absent`; ES `05-000:443:469` continues from `María López` into
  `— portátil antiguo visible`.

The same ordinary phrase can be (c) when the predicted interval extends a gold name,
or (d) when emitted independently. A standalone incorrectly predicted subword is not
classified as a boundary error merely because it is a partial word.

## Concrete follow-ups

**Data fixes — next work in klusai-datasets.** No gold-gap correction is substantiated
by this inventory. Keep current gold frozen. In `gateway_authoring_v3.expense_export`
and `public_material`, with the language fields in `prose-v3.json`, make
retention intent explicit for merchant aliases, products, headers, tariff codes and
public dates/references; add generator checks that those fields cannot accidentally
be inserted into protected spans. Pair personal DOB/address/identity examples with
public-date/product-code examples in newly authored training families. Have independent
PL/DE/NL/IT reviewers adjudicate the examples above against the guide before any policy
change. If that review finds a true omitted protected field, fix its placeholder/span
emission in `v1.splice` or its caller, annotate every repeat, and version the generator
and guide together. Do not turn predicted PERSON/ORG_PARTY into automatic gold.

**Training fixes — first priority.** Add independently authored expense exports containing
unseen merchant aliases and products, with protected person/case/account fields next
to retained shop names, headings, quantities, amounts and receipt statuses. Emphasize
Polish `kwota zgodna`, `bez poprawek`, `inna nazwa sklepu`, `nazwa skrócona`, and ordinary
post-name task notes; German `A4-Papier`, `Etikettenrolle`, `Schreibtischlampe` and
`Buchungstext`; Dutch `A4-papier` and merchant aliases; Italian `rotolo di etichette`,
`lampada da scrivania` and return-label status. Include subword/chunk-boundary variants
and the public-figure/public-statute/tariff-code confusions. Keep adjacent real personal
fields positive. Balance per conversation/family so repeated CSV cells do not dominate
training. Transfer error types only: do not copy these DEV conversations, identities,
merchant inventory, templates, or translation siblings into training.

**Decoding fixes — small, targeted experiment.** Test PERSON stopping at a verified
name/status field separator (` — `) or a parsed CSV field boundary, preserving the
name itself. Test on new DEV examples with hyphenated/multiword names, addresses and
wrapped identifiers before adoption; blanket punctuation or word-boundary trimming
could create leaks. The observed geometric boundary component is at most 0.0352 points
in any language (DE), so removing only these eight fragments cannot solve the dominant
errors. Fragmented merchant/status predictions require classification/context improvements;
merging tokens or indiscriminately dropping ORG_PARTY is not an established fix.
No proposed decoder or training change was implemented or rescored here.

Contract v3 is a **paired candidate-minus-each-comparator upper CI bound ≤ +1.0 point**,
not an absolute 1% cap on candidate over-redaction. This diagnostic has no matched
comparator results, no three-seed replication, and no held-out win claim. Improvement,
residual-leak preservation, native-human agreement, empirical semantic utility and
contract acceptance remain unverified. No gold was changed and no test scoring occurred.

## Reproduction and artifacts

[Summary JSON](validation/gateway-overredaction-summary.json) pins runtime, model/data
hashes, per-language prediction/error hashes, ledger hash, denominators and intervals.
Raw predictions, complete contextual inventories, grouped review decisions and logs are
in `/Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/overredact`.
The ledger is the authoritative adjudication; the summarizer rejects missing, extra or
duplicate annotations, character-count mismatches and cross-language provenance drift.

From this worktree, with the existing Python 3.13 MoE runtime on PATH and gateway
environment overrides unset:

```bash
export PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
AUDIT_SCRATCH=/Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/overredact
python analysis/gateway_overredaction.py --scratch "$AUDIT_SCRATCH" > "$AUDIT_SCRATCH/inference.log" 2>&1
python analysis/summarize_gateway_overredaction.py --scratch "$AUDIT_SCRATCH" \
  --ledger docs/validation/gateway-overredaction-ledger.tsv \
  --output "$AUDIT_SCRATCH/reproduced-summary.json"
COVERAGE_FILE="$AUDIT_SCRATCH/.coverage" make check
```

Inference resumes by verified DEV/model identity. No model download, cloud compute,
paid API, publication, gold edit or test-prediction access is needed.
