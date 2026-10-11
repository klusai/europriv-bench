# RES-77 Codex session review

The follow-up covers **all 300 Romanian and all 300 Polish pre-registered documents**
(75 per stratum, sampling seed 77, one sampling seed). Both configurations remain **dev**.
This is an LLM linguistic review, not a native-speaker or human certification. No model-performance
win is claimed. See the [RO report](ro-realskeleton-v1-panel-report.md) and
[PL report](pl-realskeleton-v1-panel-report.md) for estimates, denominators, CIs and gates.

## Procedure and provenance

The same Codex session read every sampled raw text, using KP 0.2.0 and the frozen rating anchors.
It did not inspect sampled gold or another judge's annotations before freezing Stage A for each
language. It had read the protocol, taxonomy, previous failed-run diagnostics and illustrative
unit tests; this is not an independently blinded experiment with fresh contexts per document.
All texts came from the existing pinned local sample; there were no new corpora, searches,
external enrichment, paid API requests, GPU jobs or dataset downloads.

The session wrote `codex-annotations-ro.jsonl` and `codex-annotations-pl.jsonl` incrementally by
reviewed stratum. Because each stratum repeats one template, mechanical transcription code
located the reviewed raw-text fields, assigned the session's chosen labels, and calculated Unicode
character offsets. It did not read gold, supply the ratings, or invoke another model. Repeated
reasons describe repeated defects; they are not independent evidence from multiple reviewers.
Every span includes its literal text and is checked against `text[start:end]` without normalization.
Each language has 3,150 annotated spans. Names in addresses stay inside the complete address;
clinical honorifics are excluded, hospital names exclude the generic ward heading, and every
repeated date, person mention and CNP/PESEL mention is included. Durations and unspecified legal
provisions are not treated as absolute dates or specific statute references.

A was frozen to scratch before gold comparison. Stage B then examined every symmetric-difference
operation. Only the `gold_errors` and review-status fields were added/updated; A spans, ratings,
reasons and artifacts remain frozen. Per-record hashes and the reconstructable pre-review JSONL
hashes are verified by `load_codex`. The [manifest](codex-review-manifest.json) records source,
licence, protocol/sample hashes, file hashes and known model metadata. The exact backend snapshot,
temperature and inference seed are unavailable; the session cannot claim the paid judges' frozen
request parameters or five-document independent contexts. This is one review run, not multiple
inference seeds. The existing `text_sha256` hashes the JSON-encoded text via protocol `digest`;
`raw_utf8_sha256` additionally records the direct UTF-8 hash.

## Findings

Romanian has coherent gender agreement and no cedilla-form `ş/ţ/Ş/Ţ` in the 300 texts. All documents
have spaces before punctuation. Administrative sender contacts reproduce the recipient's name;
clinical histories invoke absent symptoms/treatment schemes; contracts never specify their services.
County-only addresses and occasional role-name collisions reduce plausibility. These are linguistic
and internal-coherence observations, not clinical, legal or postal-registry validation.

Polish adds uninflected hospital-region phrases (75/75 clinical), feminine `Pacjentka` with masculine
`zgłosił się` (40/75 clinical), and feminine declarations retaining `legitymujący`/`świadomy`
(37/75 declarations). All 75 contracts leave representatives' names in the nominative after `przez`.
All 75 notices retain `Pana/Pani` and awkward full-name salutations. Postal-code/city combinations
look synthetic, but no postal registry was checked and they are not certified mismatches here.
These counts describe this fixed sample; the reports provide uncertainty for the scored aggregate
metrics, not separate inferential claims for each qualitative observation.

In each language, all 75 clinical documents have two gold-label disagreements: hospital
`ORG_PARTY → FACILITY` and treating physician `PERSON → PROVIDER`. Thus there are 150 disputed
span labels and 300 add/remove operations per language, with **no boundary disagreements**.
KP's native clinical refinements and the frozen instruction to choose the most appropriate type
support these suggestions; they remain single-judge hypotheses pending adjudication. No original
gold, majority overlay, leaderboard row or published dataset was changed.

## Computation and verdict

`alpha_documents` and `bootstrap` now accept explicit judge lists while retaining the original
three-judge defaults. The reports retain the original gates and add Codex-vs-gold, per-stratum
statistics and a complete-case four-judge computation. Missing judgments are never converted into
ABSENT votes. With no valid original judges, four-judge complete n is zero and panel alpha is
undefined. Codex-vs-gold uses the union of those two available raters' exact spans.

All CIs use the existing 2,000 document-cluster bootstrap draws, stratified by document type,
seed 7701, or Wilson intervals for proportions. Alpha CIs collapse because each stratum has the
same label/count structure and disagreements; that does not imply certainty beyond these templates.
The 300/300 single-judge artifact rate is not a majority rate. Codex's descriptive checks cannot
replace the frozen three-family requirements, change thresholds or authorize promotion.

Reproduce locally (Python 3.13, panel extra), preserving the original execution scratch:

```sh
python analysis/panel_report.py \
  --scratch /Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/res77-panel \
  --codex-dir docs/validation --out docs/validation \
  --overlay-out /Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/res77-codex
make check
```

The command is offline. The original unresolved paid-request liability is preserved, not retried.
Without `--codex-dir`, report generation reproduces the original frozen audit without the supplement.
The [generator fix list and patch](codex-ro-quality-fixes.md) are a separate handoff; applying them
to a future generator would change outputs and requires a new revision and fresh held-out protocol.
Agreement is not privacy accuracy, human IAA, language competence certification, clinical correctness,
legal validity or real-world representativeness. Bootstrap CIs omit judge and template-family
uncertainty. Those properties and performance on a repaired configuration were not verified.
