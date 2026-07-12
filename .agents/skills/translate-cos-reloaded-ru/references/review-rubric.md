# Independent Review Rubric

## Pass threshold

Rate every category from 0 to 5:

- 0: absent, fundamentally wrong, or not reviewed
- 1: severe failures throughout
- 2: major failures outweigh correct work
- 3: broadly understandable but not publication-ready
- 4: professional and correct, with at most minor refinements
- 5: fully verified and publication-ready at the project's quality ceiling

Convert ratings to a weighted score out of 100 with `weight × rating ÷ 5`:

- Fidelity and completeness: 30
- Mechanics and logical conditions: 25
- Terminology, names, and voices: 15
- Idiomatic Russian and register: 15
- Navigation and cross-file consistency: 10
- Typography and polish: 5

Add the six weighted results without an extra normalization step. Pass only at 90 or higher, with no blocker or major issue unresolved and no category below 4/5. Review all rules, statblocks, tables, conditionals, new terms, read-aloud blocks, dialogue, verse, and letters; do not rely on sampling for these.

Review only against the authority snapshot named by the current passing written QA report: `glossary.tsv`, `style-watch.tsv`, `style-guide.md`, and `voice-cards.md`. If any of those files changes, both role passes become stale and both reviews must be performed again after fresh QA.

## Severity

- **Blocker:** omission, added event, wrong actor/target, reversed success/failure, altered mechanic/value, broken structure/link, ruleset conversion, or meaning that could materially change play.
- **Major:** substantial nuance/voice/register loss, inconsistent key term/name, ambiguous procedure, mistranslated clue, or repeated unnatural construction.
- **Minor:** localized awkwardness, punctuation, typography, or a nonrecurring imprecision that does not change play.
- **Note:** optional refinement with no correctness impact.

## Fidelity and mechanics pass

Check sentence and block correspondence. For each procedure, identify actor, target, trigger, modality, condition, success branch, failure branch, timing, duration, frequency, range, direction, quantity, resource cost, and result. Check negation and words such as `only`, `unless`, `otherwise`, `before`, `after`, and `until` explicitly.

Verify all numeric expressions and formula contexts, not only the tokens. Confirm repeated statblocks/features match their canonical translation. Confirm 2014, 2024, and Reloaded-homebrew scopes have not drifted.

## Russian literary pass

Read the target independently before comparing difficult passages. Use `russian-prose-quality.md` to check natural syntax, information flow, rhythm, concrete imagery, dialogue voice, relationship-specific address, and register changes. Flag calques, bureaucratic filler, fake archaism, generic gothic clichés, accidental comedy, monotony, excessive embellishment, and source-shaped punctuation. Prefer the minimum correction that preserves already-natural adjacent Russian.

Read player-facing descriptions aloud. For verse, riddles, letters, and puns, judge function and voice rather than word-for-word similarity.

Inspect every structured `style_flags` occurrence in the current QA report. A match is not proof of a defect. If it is a defect, require a correction and fresh QA so the flag disappears. If it remains, disposition its exact key as `accepted-context` or `false-positive` with a sentence-specific reason. Missing, extra, duplicate, unexplained, or stale dispositions prohibit a Russian-style pass.

## Terminology and navigation pass

Check approved glossary use and natural inflection. Flag forbidden variants and inconsistent capitalization. Check visible wiki-link aliases, translated headings, cross-file references, page citations, image references, and recurring title translations.

## Finding format

For each actionable finding, provide:

- severity;
- target path and tight line/heading location;
- source meaning or invariant;
- current Russian problem;
- concise correction direction, without rewriting unrelated prose.

End with all six 0–5 category ratings, the weighted total, issue counts by severity, and `pass` or `fail`. A clean report must still state what high-risk material was checked and confirm exact disposition coverage for current style-watch flags.

For a `consistency_review` caused by generated inbound heading-link changes, use the separate `revalidate-links` path instead of these six literary/mechanical scores. The reviewer must be independent from both the completed inbound unit's original translator and the triggering heading unit's translator, and must document the exact destinations, anchors, and visible aliases checked.

The navigation reviewer cannot disposition a new or altered style-watch occurrence alone. If an implicit label changes the fingerprint, require a second Russian-style delta reviewer, independent from both translators and the link reviewer, to cover every current flag with identity-bound notes/dispositions. A genuine defect must be fixed and resynchronized rather than dispositioned.

## Separate raster review

Do not submit a raster asset through the text-unit scoring command. For a confirmed text-bearing asset, compare its pinned blob and localized candidate side by side; verify a complete source transcription, Russian meaning and typography, unchanged filename/format/dimensions, composition and legibility, and the rendered result in every path listed in `embedded_by`. Record reviewer identity, evidence, and outcome in the visual inventory before setting the asset to `completed`.
