# Russian Translation Standard

## Authority and purpose

Translate meaning first, table usability second, and literary finish third. Never improve prose by changing facts, agency, stakes, chronology, rules, or spatial relations.

Use `russian-prose-quality.md` for the target-only native-ear pass and contextual anti-calque diagnostics. Its examples are questions for an editor, not forbidden-token substitutions.

Apply authority in this order: explicit user decision, approved glossary, approved style/voice decision, established Russian D&D 5e terminology for the pinned edition, reviewed project precedent, then a documented candidate.

## Source registers

### GM procedure

Use direct, compact Russian. Preserve who acts, what triggers the event, what is automatic, what requires a check, and what happens otherwise. Translate `can`, `may`, `must`, `only`, `unless`, `until`, `before`, `after`, `on a success`, and `on a failure` with deliberate precision.

`You` normally addresses the GM outside read-aloud text. `Player` sometimes means the human player and often stands metonymically for the character; decide from the action being described. A human makes choices or describes a character, while a character walks, attacks, sees, or takes damage.

### Read-aloud prose

Use vivid, natural Russian in the present tense. Preserve the order in which details are revealed, sensory focus, distance, direction, and sentence-length rhythm. Restructure syntax when Russian requires it, but do not add adjectives, intensifiers, symbolism, or conclusions.

Avoid repetitive `вы видите`, mechanical participial chains, and English noun stacks. Prefer concrete verbs. Keep deliberate fragments and repetitions when they control pacing.

### Design and lore notes

Render analytical concepts idiomatically. Do not calque terms such as `load-bearing`, `critical path`, `scaffolding`, `stakes`, or `resonance` without considering their narrative-design sense. In NPC profiles, `Resonance` describes the intended emotional response at the table, not a magical phenomenon.

### Dialogue and voice

Maintain a living voice card for recurring speakers: form of address, `ты/вы`, social register, rhythm, favored vocabulary, humor, and relationship-dependent changes.

- Keep Strahd polished, controlled, courtly, and possessive; avoid camp villain theatrics.
- Keep Rahadin formal, quiet, and cold.
- Keep Lady Wachter refined, pragmatic, and guarded.
- Keep Van Richten educated, terse, gruff, and burdened by guilt.
- Keep Ireena emotionally direct, earnest, stubborn, and defiant.
- Preserve Rictavio's theatricality and wordplay.
- Recreate marked dialects functionally; never mimic a foreign accent through demeaning misspelling.
- Keep Madam Eva sparse, solemn, and prophetic.

Do not flatten every character into neutral literary Russian.

### Letters, verse, riddles, and props

Match the document's purpose and speaker. Translate formal letters with period-appropriate dignity but no fake archaism. Transcreate rhyme, meter, puns, slogans, and riddles so their function survives. Record nonliteral solutions in the decision log and require a second literary review.

### Rules and statblocks

Use one approved Russian D&D 5e term for each mechanic. Preserve dice, values, ranges, durations, action types, recharge/frequency, damage types, conditions, success/failure logic, and order of operations. Do not import PF2e terminology or convert a 2014 rule into its 2024 version.

The source is D&D 5e with a 2014 baseline, Reloaded homebrew, and a few explicitly cited 2024 stat elements. Keep those islands exactly scoped.

## Tonal progression

- Early Barovia: isolation, decay, tactile unease, and bodily horror.
- Vallaki: social pressure, black humor, domestic tragedy, and political ambiguity.
- Ravenloft: courtly menace and psychological horror.
- Late arcs: myth, guilt, sacrifice, redemption, and cosmic stakes.
- Epilogue: earned warmth and hope that do not erase grief.

Do not make the whole campaign uniformly archaic, purple, bleak, or solemn.

Identify the source-supported dominant effect of each atmospheric passage and preserve it. Do not replace grief with generic horror, restraint with solemnity, or black humor with unbroken gloom.

## Russian prose and typography

- Use `ё` consistently where it aids reading and in approved names.
- Use Russian quotation marks: `«…»`, then `„…“` for a quotation inside a quotation when needed.
- Use an em dash with spaces in prose; preserve source punctuation when it is technical or structural.
- Prefer natural Russian information order over English syntax.
- Avoid bureaucratic filler: `данный`, `является`, `осуществляется`, `имеет место`.
- Avoid fake archaism: `сей`, `оный`, `коего`, `дабы`, unless the speaker or artifact truly calls for it.
- Avoid generic gothic filler such as `леденящий ужас`, `зловещая тьма`, `древнее зло`, or `роковой`, unless supported by the source.
- Do not euphemize violence, abuse, coercion, or horror, but do not intensify them either.
- After restructuring a sentence, reverse-check every proposition: preserve it exactly once and add no actor, causal link, image, explanation, or degree of certainty.
- Fix the smallest span that resolves an editorial defect. Preserve already-natural adjacent Russian unless fidelity, voice, terminology, or continuity requires a wider change.

## Names and morphology

Record each recurring proper noun with gender, animacy, particle capitalization, declension, adjectival/demonym forms, title, and forbidden variants. Distinguish `Vistana` from `Vistani`, ordinary `mist` from the supernatural `Mists`, and ordinary dark powers from the setting's `Dark Powers`.

Keep file paths and link targets in their source-language filenames. Translate visible aliases and heading labels through the heading map.

## Terminology memory

Treat approved glossary rows as binding within their recorded scope. Inflect approved lemmas naturally. Put uncertain or context-dependent choices into `term-candidates.tsv` with evidence; do not guess silently.

Only promote terms after review of the actual sentence. Finalize approved glossary, style-watch, style-guide, and voice-card changes before the final QA and independent-review snapshot. A later authority edit invalidates QA and both role reviews, so rerun all three gates before learning or completion. When a decision changes, list forbidden old variants and regression-scan completed units. Never learn terminology from an unreviewed draft or bulk-import a legacy translation.

Store recurring Russian-prose diagnostics in `style-watch.tsv`. Only approved rows scan, and every match remains a warning until a Russian-style reviewer either fixes it and reruns QA or records an exact contextual disposition. Record new patterns as candidates; never promote them automatically from a scanner hit, draft, or retrospective.

Legacy PF2e, Draw Steel, home-game, and other off-branch glossaries are discovery sources only. Harvest one active-unit proposal at a time with pinned source evidence. Current approved authority always wins; never bulk-import a source's claim to be canonical.

## Final language pass

Read the Russian target once without the source, then compare it against the source. Check every paragraph for omitted meaning, calques, accidental repetition, ambiguous pronouns, misplaced negation, inconsistent address, inflated tone, and source-shaped syntax. Read read-aloud text aloud in Russian. Check rules text as executable instructions, not merely prose. Resolve every current style-watch flag explicitly.
