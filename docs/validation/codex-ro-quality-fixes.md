# Concrete Romanian generator fixes from the Codex review

The reviewed dataset revision stays unchanged. The [frozen protocol](panel-protocol.md) requires:
“Generator changes outside this assigned worktree must be delivered as a reviewable patch/instructions,
not edits in another worktree.” The generator lives in `klusai-datasets`, outside this worktree.
Accordingly, the clear changes are implemented in the [reviewable patch](codex-ro-generator-fixes.patch)
and applied/tested on source snapshots in assigned scratch. The owning checkout was only read.

Patch base: `klusai-datasets` commit `736665aa1c8908c73f6d0dd19b75d4541cf97b46` (clean files).

| Source file | Original SHA256 |
|---|---|
| `klusai/privacy/datasets/data/ro_skeletons.py` | `5d121908915a0463c1ceda85a478389efad3dec99ae39721d7e5f6fdaf9603c6` |
| `klusai/privacy/datasets/data/ro_documents.py` | `d1b01695c4f98328d1522f09855daca2eecd50af121999d4916ff95c7efffd59` |

## Implemented in the patch

1. Remove spaces before commas, periods and semicolons in `ro_skeletons.py` templates.
   Example RO row 8: `Vlad Munteanu ,` → `Vlad Munteanu,`; clinical row 0:
   `lombosciatică .` → `lombosciatică.`. Edit templates before splicing so offsets are rebuilt
   correctly. Do not postprocess existing text while retaining old spans.
2. Give administrative sender contacts their own `sender_phone`/`sender_email` fields derived
   from the synthetic signer (`doctor`), replacing the recipient's contact slots. Row 8 tells
   Vlad Munteanu to contact `vlad.munteanu@…` although Maria Ionescu signs. Existing fields remain
   available for clinical/legal templates; no extra RNG draws are introduced.
3. In `ro_documents.py`, derive `Subsemnatul/Subsemnata`, `domiciliat/domiciliată` and
   `internat/internată` from the generated person's sex, with `O` labels for grammatical slots.
   This is a clear source-code defect in the adjacent toy generator, **not a finding about the
   reviewed real-skeleton sample**, whose Romanian gender agreement is already correct.

`git apply --check` and application succeeded on scratch snapshots. A local probe exercised all
10 templates over seeds 0–9 (100 fixtures, including 30 female toy fixtures), checking literal
splice offsets, strict harness BIOES projection, absence of pre-punctuation whitespace, sender
contact ownership and gender agreement. This is implementation smoke validation, not benchmark
regeneration, harness model-performance scoring or fresh panel validation. The owning repo's full
`make check` and downstream tokenizer/model effects remain for its coordinator after integration.

Coordinator application, from the assigned `klusai-datasets` worktree, using the patch path above:

```sh
git apply --check /path/to/codex-ro-generator-fixes.patch
git apply /path/to/codex-ro-generator-fixes.patch
make check
```

## Concrete changes requiring a broader generator decision

| Defect / evidence | Proposed change | Why not silently patched |
|---|---|---|
| County in place of locality, e.g. row 54 `Strada Mihai Eminescu nr. 123, Dolj` | Generate an explicit synthetic town plus county, e.g. a coherent town/county pair | Shared `ro_generators.py` supplies addresses; affects more configs and RNG/provenance |
| Row 76 `Spitalul Municipal Bihor` | Use a municipality for municipal hospital names and keep county separately | Requires the same locality model; no real hospital registry was verified |
| Row 0 `acuzând simptomatologia descrisă`, with no symptoms described | Supply a diagnosis-linked synthetic symptom history, or describe only the documented evaluation | Clinical content needs its own reviewed cases, not invented clinical guidance |
| All clinical rows `tratament conform schemei` without a scheme | Include a reviewed plan or remove the unsupported cross-reference | Changes clinical content and document completeness |
| Contracts, e.g. row 14, refer only to `serviciilor convenite de părți` | Specify the synthetic service, each party's role and concrete performance terms | A complete contract template needs deliberate content authoring |
| Hospital/physician labels in all 75 sampled clinical rows | Use FACILITY and a separate PROVIDER slot; keep legal representatives/admin signers PERSON | Single-judge taxonomy hypotheses; await adjudication before a gold migration |
| Role collisions: admin 458/705; clinical 21/1473 | Generate distinct identities for separate roles unless deliberately modeling a collision | Equal names are possible; changing sampling behavior needs a stated design |
| Potentially weak ward/diagnosis pairings, e.g. row 0 | Couple section to the authored clinical scenario | Linguistic plausibility flag, not a certified clinical impossibility |

Do not label normal official boilerplate or blank signature lines as defects merely for being
formulaic. No wrong cedilla-form Romanian diacritics were found; normalization is not needed for
this sample. No external address, banking, legal or clinical validation was performed.

The patch changes future generated text; it is not applied to any published config. There is no
accepted gold overlay and no affected leaderboard row in this run, so no rescore is warranted.
On later adoption, publish only through the coordinator under a new revision/config, rescore
changed rows through the harness when predictions/local CPU models are available, explicitly record
unavailable model rows, and pre-register fresh held-out validation. Never copy v1 scores or use
these same 300 documents to promote a repaired config.
