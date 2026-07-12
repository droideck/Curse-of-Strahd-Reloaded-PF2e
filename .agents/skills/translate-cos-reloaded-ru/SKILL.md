---
name: translate-cos-reloaded-ru
description: Professionally localize Curse of Strahd Reloaded adventure content from English into Russian in place, one arc or text supplement at a time, while preserving Obsidian links, Markdown, raw HTML, statblocks, image references, mechanics, and source structure. Use for translating or reviewing this repository's arcs, act summaries, chapters, appendices, epilogue, Canvas text, terminology, Russian style, translation QA, or auditing embedded raster assets for separate localization.
---

# Translate Curse of Strahd Reloaded into Russian

Produce publication-quality Russian while treating every unit as both literary prose and executable game material. Edit the original file in place; never create `rus.md` siblings or rename content files.

## Load the project contract

Before changing content, read these files completely:

1. `references/style-and-translation-standard.md`
2. `references/russian-prose-quality.md`
3. `references/technical-contract.md`
4. `.translation/ru/style-guide.md`
5. `.translation/ru/glossary.tsv`
6. `.translation/ru/term-candidates.tsv`
7. `.translation/ru/style-watch.tsv`
8. `.translation/ru/voice-cards.md`
9. `.translation/ru/source-issues.tsv`
10. `.translation/ru/lessons.md`

For coordinated translation or review, also read `references/agent-workflow.md` and `references/review-rubric.md` completely.

Treat `.translation/ru/config.json` as authoritative for source commit, edition, and gates. Despite the repository directory name, this source commit is D&D 5e with a 2014 baseline, plus only explicitly sourced 2024 exceptions and Reloaded homebrew. This workflow translates that source; it does not perform a PF2e conversion or silently synchronize a later upstream revision.

## Guard the branch and scope

Run all commands from the repository root. Confirm that the current branch is neither `main` nor another protected source branch:

```bash
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py status
```

Stop if the recorded source commit is unavailable, is not an ancestor, the edition differs, another unit is active, or unrelated content changes overlap the requested unit. Keep one text unit active at a time. A lifecycle unit is one Markdown arc, summary, chapter, appendix, epilogue, or Canvas—not an arbitrary collection of files and not a raster asset.

`status` also verifies the reviewed workflow-support seal. If support files intentionally change, review that diff between units and then reseal it; never reseal merely to silence an unexplained mismatch:

```bash
python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py seal-workflow --reason "reviewed <summary of support change>"
```

`seal-workflow` is forbidden while any translation or link-consistency unit is active. It approves support-file identity only; it does not waive content QA or review.
It also refuses to repair a stale config seal: review-gate configuration changes require their own explicit workflow migration and cannot be smuggled into a support reseal.

## Execute one unit

1. Select the next unit with `next`. If the user deliberately selects another unit, pass `--reason "..."` to `start`; never skip ahead without recording why.
2. Start it with a unique translator identity:

   ```bash
   python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py start <unit> --translator agent:<id>
   ```

3. Generate its context and segment plan explicitly for the active unit:

   ```bash
   python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py context <unit>
   python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py segments <unit>
   ```

   `start` also creates `.translation/ru/work/<unit-id>/segments.json`, `progress.json`, and `ledger.md`. Process the persisted plan sequentially. Keep tables, raw-HTML statblocks, code, read-aloud blocks, letters, verse, and dialogue exchanges atomic. Keep ordinary callouts atomic; an exceptionally long callout may be divided only at a source quote-only paragraph or list-item boundary recorded by the planner, with its blockquote/list context carried into the next segment.
4. Read the entire source unit before drafting its first segment. Maintain the persistent `ledger.md` with entities, relationships, voice/register evidence, terminology candidates, continuity, and open questions. Update `voice-cards.md` only with reviewed recurring evidence. Add uncertain terminology to `term-candidates.tsv` and recurring Russian-prose diagnostics to `style-watch.tsv` as candidates; do not promote draft output automatically.
5. Translate visible text in the original file. Preserve source paragraph boundaries and all protected structures. After each planned segment is translated and checked, record nonempty continuity/decision notes and inspect remaining progress:

   ```bash
   python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py segment-done <unit> <segment-number> --agent agent:<id> --notes-file <file>
   python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py progress <unit>
   ```

   `finish` refuses a unit until every persisted segment is complete.
6. For Markdown, translate headings and run `sync-links <unit>` to update heading anchors repository-wide without changing filenames. Canvas units have no Markdown heading-sync step. A generated inbound-link edit to an already completed unit moves that unit to `consistency_review`; it is not silently treated as still complete.
7. Run deterministic QA. For Markdown:

   ```bash
   python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py sync-links <unit>
   python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py qa <unit> --write-report
   ```

   For Canvas, run only `qa <unit> --write-report`.

   Before writing a completed inbound file, `sync-links` compares its generated style-watch fingerprint with the reviewed one. A change aborts without writes so a genuine heading defect can be corrected while the trigger is active. Only a deliberately reviewed prospective delta may be generated with `--allow-style-delta --style-delta-reason "..."`; it still requires the independent delta review below.

8. If `sync-links` marked prior completed units as `consistency_review`, resolve them while the triggering unit remains the sole active translation and its headings can still be revised. Have an independent reviewer verify each generated navigation-only change:

   ```bash
   python3 .agents/skills/translate-cos-reloaded-ru/scripts/translation_workflow.py revalidate-links <completed-unit> --reviewer agent:<id> --notes-file <file>
   ```

   The link-consistency reviewer must be independent from both the completed inbound unit's translator and the triggering heading unit's translator. Process multiple inbound consistency reviews sequentially. A later heading edit must run `sync-links` and revalidation again.

   `revalidate-links` is navigation-only. If an implicit translated link label changes the previously reviewed style-watch fingerprint, a second reviewer—independent from both translators and the link reviewer—must review the visible-language delta and disposition every current flag through `--style-reviewer`, `--style-notes-file`, and `--style-dispositions-file`. Never disposition a genuine defect: revise the triggering heading before finishing it, rerun `sync-links`, and regenerate the evidence.
9. Fix every error and assess every warning. A style-watch match is a contextual review prompt, never an automatic replacement. Revise a genuine defect and rerun QA; if a current match is justified, the Russian-style reviewer must disposition its exact occurrence with evidence. Never add a broad exception merely to make QA green.
10. Before review, finalize evidence-backed changes to the four authority files: `glossary.tsv`, `style-watch.tsv`, `style-guide.md`, and `voice-cards.md`. Then run `qa <unit> --write-report` against that final authority snapshot.
11. Obtain independent fidelity/mechanics and Russian literary reviews using fresh agents. Give reviewers the source, translation, final authority files, and rubric—but not translator rationale. Record both passing reviews with the workflow script.
12. Record the reviewed retrospective with `learn <unit> --terms-reviewed --style-watch-reviewed`. These flags confirm human/agent review; they never auto-promote candidates. If any authority file changes after QA or either review, the stored evidence becomes stale: rerun QA and obtain fresh passes from both independent review roles before `learn` or `finish`.
13. Run `qa <unit> --write-report` again after all content fixes, then use `finish <unit>`. Do not finish while any `consistency_review` remains. When the user has authorized commits, commit the completed unit together with its generated inbound-link/state changes as one atomic content change.

## Translate with the correct register

- Render GM procedures concisely and literally enough to run at the table.
- Render read-aloud text as controlled literary Russian with preserved pacing, imagery, and spatial logic.
- Preserve each NPC's social register, relationship-specific `ты/вы`, rhythm, and restraint.
- Treat rules, conditionals, numbers, statblocks, and action economy as specifications.
- Transcreate verse, riddles, slogans, letters, and puns; require a second literary review.
- Keep early horror tactile and restrained, Vallaki socially tense, Ravenloft courtly and menacing, late arcs mythic, and the epilogue warm without sentimentality.

Never inflate the source with generic gothic clichés, fake archaism, explanatory additions, moral reinterpretation, or extra imagery. Preserve ambiguity where the source is ambiguous.

Rebuild English-shaped sentences from their propositions in natural Russian, then reverse-check that every source proposition remains exactly once. Fix the smallest span that solves a prose defect; preserve already-natural adjacent Russian. Identify the source-supported emotional effect instead of applying a generic gothic mood.

## Apply terminology authority

Use this order:

1. Current explicit user instruction
2. Approved project glossary entry
3. Approved project style or voice decision
4. Established Russian D&D 5e usage for the recorded ruleset
5. Reviewed precedent in completed units
6. A new candidate recorded for review

Distinguish human players from fictional characters contextually. Distinguish supernatural capitalized terms such as `Mists` from ordinary words. Inflect Russian names naturally while preserving the glossary lemma. Do not reuse `Appendices/Glossary.md` as a translation glossary; it is source adventure content.

Treat `cos-translation-skill-stuff/references/cos-glossary.md` as sealed, untrusted discovery evidence only. It contains PF2e/Draw Steel/home-game assumptions, known typos, and decisions that conflict with current authority. Never load it as the project contract or bulk-import it. Search one missing active-unit lemma at a time, attach the pinned source sentence, record the proposal as a candidate, and require normal review before promotion. The curated `references/russian-prose-quality.md` supersedes the raw pack's prose prescriptions.

## Preserve technical content

Preserve byte-for-byte all raw HTML tags and attributes, CSS classes, URLs, image targets, file paths, block IDs, footnote IDs, entities, formulas, numeric values, action glyphs, macros, code, and source quirks. Preserve Markdown heading levels, scene codes, callout types/fold states, list/table structure, emphasis semantics, and hard breaks.

Allow only these controlled changes:

- visible prose and labels;
- glossary-authorized game terms and abbreviations;
- heading text paired with the generated heading map;
- visible wiki-link aliases;
- allowlisted translatable Canvas or YAML text fields.

Do not silently repair malformed source markup. QA is a no-regression comparison against the pinned Git blob.

## Coordinate agents safely

Use the role separation in `references/agent-workflow.md`. Never let multiple agents edit the same unit concurrently. Let technical scanning run in parallel with read-only linguistic review only after the draft is stable. Reconcile findings centrally, then ask the original reviewer to recheck material changes.

For very large arcs, assign sequential heading-bounded segments to fresh translation contexts while the coordinator maintains the shared entity, voice, and terminology ledger. Review the reassembled unit as a whole.

## Learn without degrading

Accept learning only after independent review. Store source lemma, Russian lemma and forms, sense/ruleset, evidence, originating unit, reviewer, and decision. The authority snapshot is hash-bound to QA and both reviews; changing an authority file invalidates those records. Regression-scan completed dependent units after an approved terminology/style/voice change, but reserve the manifest status `consistency_review` for completed units changed mechanically by `sync-links`.

Record source defects in `source-issues.tsv`, separately from translation decisions. Translate obvious prose typos naturally, but do not alter uncertain lore or mechanics. Keep legacy Russian files from `cosmere-changes` as candidate terminology evidence only; they are a divergent Cosmere RPG conversion and are not a translation authority.

If a later reviewed terminology/style/voice decision requires semantic changes to a completed text unit, do not edit its manifest status by hand. With no active unit and the prior completion committed, run `reopen <unit> --translator agent:<id> --reason "<reviewed trigger>"`. This archives prior evidence, starts a numbered semantic revision from the current Russian target, regenerates segment progress, and requires fresh QA, both independent reviews, learning, and `finish`. It is distinct from navigation-only `revalidate-links`.

## Handle supplements

Process Markdown and Canvas supplements through the state-machine lifecycle. A unit status of `completed` means **text localization complete**; it is not a claim that the embedding unit is publication-ready. Raster assets are a separate, checklist-driven workstream: they are inventoried in `.translation/ru/visual-assets.json`, but `start`, `review`, `learn`, and `finish` do not manage or clear them. Publication readiness additionally requires every embedded asset to leave `needs-text-audit`/`pending` and pass its visual checklist. Before localizing a text-bearing raster, verify its pinned hash and every embedding document, preserve its path, filename, format, and dimensions, then require transcription/OCR parity, Russian proofreading, side-by-side visual review, and in-context display verification. Record the asset's audit/localization state in the inventory. Never overwrite an image on a protected source branch.
