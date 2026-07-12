# Living Russian Style Guide

Version: 0.2

Status: initial reviewed baseline

Edition profile: D&D 5e, 2014 baseline; explicitly cited 2024 rules and Reloaded homebrew remain narrowly scoped

## Project voice

Write clear, controlled literary Russian. Preserve the guide's confidence and table-ready precision. Atmospheric passages should be sensory and rhythmic without becoming ornate; procedures should be compact without becoming bureaucratic.

The campaign's tone evolves:

- Act I uses isolation, decay, bodily unease, and mounting dread.
- Act II combines social pressure, black humor, domestic tragedy, and political ambiguity.
- Act III emphasizes courtly menace, investigation, and psychological horror.
- Late arcs expand into myth, guilt, sacrifice, redemption, and cosmic stakes.
- The epilogue permits warmth and hope while retaining the cost of what happened.

## Stable editorial decisions

- Preserve English filenames and image paths. Translate headings and visible link aliases; synchronize heading targets mechanically.
- Use `ё` consistently in running prose and approved names.
- Use `«ёлочки»` for primary dialogue quotation. Preserve technical straight quotes inside markup and source identifiers.
- Treat scene codes (`A1`, `B5a`, `U3j`) as navigation identifiers and never translate them.
- Translate obvious visible source typos naturally, but preserve malformed technical markup exactly and log uncertain lore/mechanics.
- Do not use the legacy `cosmere-changes` Russian files as prose precedent. They contain rules conversion and structural changes.
- Do not use `Appendices/Glossary.md` as a translation glossary; it defines adventure mechanics.

## Address and recurring voices

The form-of-address matrix must be expanded during context preparation for each arc. Until an interaction is reviewed, do not invent intimacy or social distance.

- Strahd: polished, courtly, controlled, possessive; menace comes from certainty, not shouting.
- Rahadin: formal, quiet, economical, cold.
- Lady Wachter: refined, pragmatic, politically careful.
- Van Richten: educated, terse, gruff, increasingly burdened by guilt.
- Ireena: earnest, emotionally direct, stubborn, and defiant.
- Rictavio: theatrical, playful, capable of third-person self-reference and wordplay.
- Madam Eva: sparse, solemn, prophetic.

For Blinsky, Cyrus, and other marked speech, recreate social effect and comic rhythm without caricaturing a real-world accent.

## Rules language

Use only `approved` D&D 5e terms from `glossary.tsv` as binding. Rows marked `provisional` are useful proposals but must be verified against an edition-specific Russian authority or an explicitly reviewed project decision before first binding use. Read every rule as executable logic. Preserve actor, target, trigger, negation, optionality, success/failure branch, order of operations, timing, frequency, duration, range, direction, quantity, and resource cost.

Do not normalize a quoted 2024 stat element to 2014, or vice versa. Do not import PF2e terms, action economy, degrees of success, or condition meanings.

`Player` follows an approved contextual rule: use `игрок` for the person at the table and `персонаж` or a natural subject for the in-world actor. Never bulk-replace it.

## Read-aloud prose

Preserve reveal order and spatial relationships. Prefer concrete verbs and natural Russian information order. Keep purposeful fragments and repetitions. Avoid habitual openings such as `Вы видите…` when the source does not foreground perception.

Read finished boxed text aloud. Remove calques and tongue-twisting participial chains without adding imagery or intensity.

## Prohibited defaults

Do not reach automatically for `леденящий ужас`, `зловещий мрак`, `древнее зло`, `сердце тьмы`, `роковой`, `судьбоносный`, `неведомая сила`, fake archaism, or bureaucratic filler. Use such language only when the source itself supports the image and intensity.

## Native-Russian editorial pass

Rebuild English-shaped sentences from meaning, then reverse-check the source propositions. Every proposition must remain exactly once; do not add an actor, causal link, image, explanation, or stronger certainty while improving syntax.

Fix the smallest span that resolves the defect. Preserve already-natural adjacent Russian unless fidelity, terminology, voice, or continuity requires a wider rewrite. Read player-facing prose aloud, then compare it against the source for omissions and inflation.

Use classical gothic qualities—restraint, controlled rhythm, concrete detail, and an educated living voice—as diagnostics, not as an imitation template. Preserve the source-supported emotional effect; do not turn grief, black humor, tenderness, or plain procedure into generic dread.

`style-watch.tsv` is a reviewed warning memory. Its matches require contextual assessment, never automatic replacement. Correct real defects and rerun QA; independently disposition justified surviving matches. The initial baseline may bootstrap only exact high-signal diagnostics from a sealed raw reference or a repository-recorded excerpt and source hash, plus independent review; after translation begins, add new patterns as candidates and promote them only from a pinned lifecycle-unit source/target sentence.

The supplied `cos-translation-skill-stuff` pack is provenance-only. Its PF2e, Draw Steel, and home-game rules and glossary are not authority. Mine a missing active-unit lemma individually, attach pinned-source evidence, and route it through `term-candidates.tsv`.

## Decisions still requiring contextual review

- Full `ты/вы` relationship matrix for recurring NPCs.
- Singular/plural/adjectival forms for `Vistana` and `Vistani`.
- Project-approved Russian terms for Reloaded-only conditions and Challenge Ratings 2.0, checked against published D&D terminology specifically to prevent collisions.
- Campaign-specific artifact, faction, deity, calendar, and title capitalization.
- Transcreation of the Death House verse, prophecies, slogans, riddles, and puns.

### Homebrew condition collision gate

Do not promote a Reloaded condition until its label convention and masculine/feminine/neuter/plural forms are recorded. Check collisions by mechanics, not surface similarity:

- `Bloodied` is only a half-HP threshold and does not necessarily describe visible blood.
- `Dazed` must remain distinct from established `Stunned` terminology.
- `Hindered` must not imply `Restrained`, `Grappled`, or physical binding that its rules do not impose.
- `Slowed` must remain distinct from the *slow* spell and any explicitly scoped 2024 mechanic.

## Reviewed evolution log

Add only reusable decisions that survived independent review. Include date, originating unit, evidence, old behavior, new rule, and affected completed units. Keep one-off sentence fixes in that unit's review report.

### 2026-07-12 — workflow quality refresh

- Origin: supplied `ru-gothic-prose` material and comparative audit against the pinned D&D 5e workflow.
- Accepted: proposition-first restructuring, minimum-change editing, source-effect preservation, contextual anti-calque warnings, and explicit reviewer dispositions.
- Rejected: Draw Steel term invariance, bulk legacy glossary authority, universal NPC speech stereotypes, blanket passive/word bans, meaning-changing gothic synonym swaps, and incorrect nested-quote guidance.
- Affected completed units: none; translation has not started.
