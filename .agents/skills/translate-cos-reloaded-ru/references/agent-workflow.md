# Arc-by-Arc Agent Workflow

## Roles

### Coordinator

Own the branch, active-unit lock, source baseline, segmentation, shared context, final reconciliation, and state transitions. Be the only role allowed to combine findings or finish a unit.

### Terminology and context curator

Read the whole source unit, its direct cross-links, approved glossary, prior lessons, and relevant character voice cards. Produce a compact ledger of entities, titles, mechanics, forms of address, recurring phrases, and uncertain terms. Do not draft the translation.

### Translator

Translate one heading-bounded segment at a time in source order. Read the unit-level ledger before every segment. Preserve complete structural blocks and update the ledger with new candidates. Never edit a segment concurrently with another translator.

### Fidelity and mechanics reviewer

Compare source and Russian text in a fresh context. Audit completeness, actor/target, conditions, logical branches, values, timing, action economy, statblocks, tables, and terminology. Report findings without silently rewriting.

### Russian literary reviewer

Read the Russian as a professional editor while consulting the source for intent and `russian-prose-quality.md` for the native-ear pass. Audit naturalness, rhythm, register, voice, `ты/вы`, dialogue, typography, calques, clichés, and tonal progression. Report findings without silently rewriting. Resolve every structured style-watch occurrence against its exact sentence.

### Technical verifier

Run deterministic QA, inspect warnings, validate link synchronization, and confirm that no new structural defect exists. The verifier does not waive a linguistic issue merely because the scanner passes.

## Lifecycle

Use exactly one active unit:

`pending → in_progress → auto_qa_pass → independent_review → approved → completed`

Here `completed` means the Markdown/Canvas text lifecycle is complete. It does not certify publication readiness while an embedded raster remains `needs-text-audit` or `pending` in the separate visual inventory.

Use `needs_revision` for a failed review, `stale_source` when the baseline blob changes, and `skipped` only with a recorded reason such as an empty source placeholder. A completed unit changed only by generated inbound heading-link synchronization follows a separate transition:

`completed → consistency_review → completed`

Only `revalidate-links` closes that navigation-only review. Do not use `consistency_review` as a generic label for terminology or prose revision.

## Between-unit workflow changes

`status` compares workflow-support files with the reviewed seal. If an intentional skill, reference, script, test, agent configuration, `.gitignore`, or visual-inventory change breaks that seal, inspect the diff with no active unit and run:

```bash
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py seal-workflow --reason "reviewed <summary of support change>"
```

Never run this command to bless an unexplained mismatch. It cannot run while a translation or `consistency_review` unit is active and does not replace content QA or independent review.

### 1. Preflight

Run:

```bash
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py status
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py next
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py context <unit>
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py segments <unit>
```

Confirm source edition, branch, blob hash, source maturity, related completed units, and cross-links. Resolve critical terminology before translating it.

### 2. Start and segment

Start with `start <unit> --translator agent:<id>`. If an explicit user request selects a unit other than `next`, add `--reason "..."`; the manifest must retain that departure from sequence. Start creates a persistent work area at `.translation/ru/work/<unit-id>/` containing the source-derived `segments.json`, completion `progress.json`, and shared `ledger.md`.

For files above the configured segment size, use safe heading or paragraph boundaries while keeping tables, raw-HTML statblocks, code, read-aloud text, letters, verse, and dialogue exchanges intact. Keep ordinary callouts whole; the planner may divide an exceptionally long callout only at a quote-only paragraph or list-item boundary and records the continuation prefix. A truly indivisible block may remain explicitly marked oversize. A large arc remains one lifecycle unit even when multiple fresh contexts translate it sequentially.

Pass each translator:

- exact source segment and current target location;
- approved glossary and relevant candidates;
- unit entity/voice ledger;
- style and technical contracts;
- immediately preceding translated context for continuity.

Do not pass later plot text unless needed for disambiguation. Do not ask parallel agents to patch the same file.

After translating and checking each persisted segment, place a concise summary of decisions, continuity, and unresolved concerns in a notes file, update the shared ledger, then record completion:

```bash
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py segment-done <unit> <segment-number> --agent agent:<id> --notes-file <file>
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py progress <unit>
```

The notes file must be nonempty. `finish` requires every segment in persistent progress to be `completed`; an agent's informal claim is not sufficient.

### 3. Reassemble and synchronize

Have the coordinator read the entire Russian file for continuity, repeated terms, heading hierarchy, and segment seams. For Markdown, run `sync-links <unit>` once headings are stable. Skip this command for Canvas units.

`sync-links` may update pending inbound files mechanically. Before writing a previously completed inbound unit, it compares the prospective style-watch fingerprint with the reviewed report and aborts without writes on a delta. Correct a genuine heading defect while the trigger remains active. Only after inspecting a justified prospective delta may the coordinator rerun `sync-links <unit> --allow-style-delta --style-delta-reason "<what was reviewed>"`; this acknowledgement is not a pass and does not replace the independent delta review. A written completed inbound update becomes `consistency_review` with the triggering unit, translator, before/after hashes, and any acknowledged preflight recorded.

### 4. Automated QA

Run `qa <unit> --write-report`. Treat protected-token, numeric, structure, Canvas topology, and new broken-link failures as blockers. Manually assess warnings for source quirks, approved Latin terms, potential English leakage, and structured style-watch flags. A style-watch match is not proof of an error and must never trigger automatic replacement.

### 5. Freeze authority and obtain independent review

Before asking for final reviews, resolve candidate terms and prose patterns, then make all approved changes to `glossary.tsv`, `style-watch.tsv`, `style-guide.md`, and `voice-cards.md`. Run `qa <unit> --write-report` again after the last authority edit. QA and both review records are bound to the source, target, workflow, and this four-file authority snapshot.

Give each reviewer only the source blob, Russian candidate, the final authority files, and `review-rubric.md`. Do not give translator explanations or suspected answers. Reviewers must cite tight source/target locations and classify severity.

Record only a genuine pass:

```bash
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py review <unit> --role fidelity --reviewer agent:<id> --fidelity 5 --mechanics 5 --terminology 4 --language 4 --navigation 5 --typography 5 --verdict pass --blockers 0 --majors 0 --minors 0 --notes-file <file>
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py review <unit> --role russian-style --reviewer agent:<id> --fidelity 4 --mechanics 5 --terminology 5 --language 5 --navigation 5 --typography 5 --verdict pass --blockers 0 --majors 0 --minors 0 --notes-file <file> --style-dispositions-file <json>
```

Omit `--style-dispositions-file` only when the current QA report has no `style_flags`. Otherwise provide this identity-bound shape and cover every current key exactly once:

```json
{
  "schema_version": 1,
  "unit_id": "arc-a",
  "target_sha256": "<current QA target hash>",
  "style_flags_sha256": "<current QA style fingerprint>",
  "dispositions": [
    {"key": "RUQ-001:<occurrence hash>", "decision": "accepted-context", "reason": "Specific source/voice justification."}
  ]
}
```

Allowed decisions are `accepted-context` and `false-positive`, each with a nonempty sentence-specific reason. A corrected defect must disappear from a freshly written QA report; do not disposition stale flags as fixed.

A failing Russian-style review may omit the dispositions file when one or more matches are genuine defects. Describe those defects in the review notes, revise the target, and generate fresh QA before attempting a pass.

After fixes, rerun deterministic QA and return changed passages to the original reviewer. A different reviewer may replace them only if independence is preserved and the change is recorded. If any authority file changes after QA or after either review, rerun QA and obtain fresh passes for both roles; one new review cannot make the other role's stale record current.

### 6. Curate learning

Confirm every term and style-watch candidate was reviewed and record the retrospective. Authority promotion belongs before the final QA/review snapshot; do not edit an authority file between the passing reviews and this command. The confirmation flags never promote rows automatically:

```bash
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py learn <unit> --curator agent:<id> --lesson-file <file> --terms-reviewed --style-watch-reviewed
```

When an authority decision changes, regression-scan completed dependent units (for example with read-only `qa --all-completed`) and schedule semantic revision where needed. Do not assign the link-specific `consistency_review` state merely because an authority hash changed.

For each affected completed unit, commit the prior completion first and, with no active unit, run:

```bash
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py reopen <unit> --translator agent:<id> --reason "<reviewed authority decision and impact>"
```

`reopen` archives the prior QA/review/learning evidence, records a revision history entry, and restarts the full segment → QA → two reviews → learning → finish lifecycle from the current Russian file. Never emulate this transition by editing the manifest. Use `revalidate-links` only for generated navigation changes with no semantic prose change.

### 7. Finish

Run `qa <unit> --write-report` again so its report matches the final target hash. Use `finish <unit>` only when all persistent segments are complete, both independent reviews match the current authority/workflow identity, learning is current, and all hard gates are green.

If `sync-links` produced completed inbound `consistency_review` units, keep the triggering unit active while its headings are still revisable. Give each navigation-only diff to a reviewer independent from both that completed unit's original translator and the triggering heading unit's translator, require nonempty notes describing the checked targets/aliases, and run each review sequentially:

```bash
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py revalidate-links <completed-unit> --reviewer agent:<id> --notes-file <file>
```

This command verifies the expected generated hash, runs deterministic QA, records a link-consistency review, and returns that unit to `completed`. If the current structured style-watch fingerprint differs from the prior Russian-style pass, visible linguistic evidence changed—even through an implicit translated link label. A genuine defect must be fixed by revising the triggering heading before it is finished and rerunning `sync-links`. A justified surviving delta requires a separate reviewer, independent from both translators and the link reviewer, plus nonempty notes and an identity-bound disposition file covering every current flag:

```bash
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py revalidate-links <completed-unit> --reviewer agent:<link-id> --notes-file <link-notes> --style-reviewer agent:<style-id> --style-notes-file <style-notes> --style-dispositions-file <json>
```

The resulting link-consistency record binds the prior semantic fingerprint, current fingerprint, current target, exact dispositions, and both reviewer identities. Resolve every such unit before final QA/reviews/learning/finish for the trigger; any later heading change repeats synchronization and revalidation.

## Raster-asset checklist

Raster files are not text lifecycle units and are not governed by the unit state machine. `.translation/ru/visual-assets.json` deterministically inventories every local raster embedded by the pinned Markdown/Canvas source, plus explicitly retained supplemental candidates. For an asset that contains player- or GM-visible English:

1. Verify the source SHA-256, dimensions, format, and complete `embedded_by` list against the pinned commit.
2. Transcribe the visible source text and record uncertain readings before editing.
3. Translate with the same glossary, voice, ruleset, and literary standards as the embedding unit.
4. Preserve the referenced path and filename, pixel dimensions, composition, hierarchy, and legibility unless the user explicitly approves a migration.
5. Obtain independent Russian proofreading and side-by-side visual/OCR parity review.
6. Open every embedding document and verify the localized asset at its actual display size.
7. Update only the asset status and reviewed evidence in the visual inventory; do not run `start`, `review`, `learn`, or `finish` for the raster.

`needs-text-audit` means the asset is embedded but has not yet been classified. `pending` means visible English is confirmed and localization/review remains. Do not infer that an unclassified portrait or map is safe merely from its filename.

When commits are authorized, commit one completed unit plus its mechanical inbound-link/state changes. Do not bundle the next unit.

## Review loop

The coordinator should normalize findings into one issue list, but preserve reviewer wording and severity. Fix blockers and majors first, then minors. Never resolve contradictory reviews by majority vote; return to source meaning, glossary authority, and explicit project decisions.

## Self-improvement safeguards

- Never learn from a draft merely because it sounds fluent.
- Never bulk-promote machine-extracted terms.
- Store rejected variants so recurring errors become detectable.
- Store recurring prose diagnostics as candidates in `style-watch.tsv`; promote only from sentence-level evidence and independent review.
- Require exact dispositions for surviving approved style-watch occurrences; never treat a warning as a mechanical replacement order.
- Attach decisions to source evidence and a reviewer.
- Regression-review affected completed units after a term change; do not confuse this with link-only `revalidate-links`.
- Keep source defects separate from Russian style decisions.
- Treat legacy Cosmere Russian files as untrusted candidate evidence only.
