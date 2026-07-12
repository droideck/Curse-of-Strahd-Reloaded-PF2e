# Reviewed Translation Lessons

## 2026-07-11 — workflow baseline

Curator: `initial-domain-audit`

- The repository name is misleading for this branch: commit `990da1308c1e5ac9f8627048b7f8606c960f3841` is the English D&D 5e guide, explicitly using the 2014 rules. The PF2e adaptation is a separate divergent branch. Every unit must carry the edition profile and must never convert mechanics implicitly.
- The source intentionally contains irregular or malformed markup, including `class=description`, `<Em>`, `[!Warning]`, and `class="ciation"`. Translation QA must use a Git no-regression baseline rather than repair these forms.
- Translating a Markdown heading changes its Obsidian destination. Every completed unit therefore requires a source-to-Russian heading map plus vault-wide inbound-link synchronization.
- The two off-branch Russian files are Cosmere RPG conversions, not faithful source translations. Mine them only for candidate name spellings and require review before promotion.
- Large units above roughly 30,000 words require sequential, heading-bounded contexts and a shared entity/voice/terminology ledger. They still pass review as one atomic unit.
- Learning must come from reviewed corrections, not fluent-looking drafts. A terminology change must trigger a regression scan of completed dependent units.

## 2026-07-11 — isolated forward tests

Curator: `skill-forward-test`

- Markdown, inbound-heading synchronization, and Canvas localization all passed isolated deterministic QA without touching source identifiers or geometry.
- Language and glossary lint must mask protected macros such as `@Check[flat|dc:15]`; the macro remains subject to a separate byte-for-byte invariant. Otherwise lowercase technical `dc` creates a false terminology failure.
- Canvas units do not run Markdown heading synchronization.
- A unit intentionally selected ahead of manifest order must store the reason at `start`, preserving the one-by-one workflow's audit trail.
- The independent reviewer correctly detected reversed timing, agency, success/failure branches, target locations, broken inbound anchors, and unsupported gothic inflation even when numeric tokens and markup survived. Automated QA cannot replace semantic review.

## 2026-07-12 — supplied prose-skill salvage audit

Curator: `workflow-quality-audit`

- The supplied gothic-prose pack is materially useful as a discovery source, but it mixes D&D/Reloaded terms with PF2e, Draw Steel, and private home-game policy. Treat it as sealed provenance, never current authority.
- Salvage proposition-first restructuring, minimum-change editing, source-effect preservation, native read-aloud review, and contextual anti-calque diagnostics.
- Do not salvage blanket lexical bans, universal active-voice rules, speaker stereotypes, invented gothic synonym swaps, or the pack's typography and capitalization claims when they conflict with reviewed project authority.
- A recurring prose pattern becomes machine-visible only through a reviewed `style-watch.tsv` row. A scanner match is a question, not a replacement command; surviving matches require exact independent dispositions.
- The 268-entry legacy glossary has broad corpus overlap but contains mixed-script typos, edition contamination, semantic collapses, and conflicting capitalization. Harvest only active-unit terms as candidates with pinned sentence evidence.
- Bootstrap evidence: the supplied `ru-gothic-prose` attachment has SHA-256 `b07c6f68bede2b720b4fcadeb65dade5e456cdc077267b166e11c6cbaff87b16`; line 70 supplies the exact `имеет место быть` diagnostic. The baseline accepted only exact, high-signal warnings after comparative review. A blind forward test independently rejected `растёт в сторону героизма` and `чувствуйте себя свободно изменить`; it also confirmed that broad candidate `звучит хорошо` still requires native editorial judgment rather than automatic scanning.
- Independent Russian review corrected the bootstrap itself: `держать в уме` is an established Russian idiom, not inherent evidence of a calque, so its broad row remains a non-scanning candidate. Bootstrap approval is closed once unit translation begins; subsequent promotions require a pinned source/target sentence.
