# Russian Prose Quality Pass

Use this reference while drafting Russian prose and during the independent Russian-style review. It is an editorial diagnostic, not terminology authority and not a replacement table.

## Rebuild the sentence in Russian

Translate propositions, not English surface order. First identify actor, action, object, condition, modality, causal link, degree of certainty, image, and information order. Then rebuild them in natural Russian.

After splitting, merging, or reordering a sentence, reverse-check its propositions:

- preserve every source proposition exactly once;
- preserve actor, scope, negation, modality, chronology, and causal relation;
- add no proposition, image, explanation, motive, or emotional intensity;
- remove no ambiguity merely because Russian permits a more explicit sentence.

Prefer a concrete verb when an English-shaped nominal construction makes Russian heavy. Prefer an active or impersonal construction only when it preserves agency and focus; passive voice is not inherently wrong.

## Match the source register

| Source register | Russian target |
|---|---|
| GM procedure | Direct, compact, operational; logical branches unmistakable. |
| Read-aloud | Controlled literary Russian; source-led sensory order, rhythm, and restraint. |
| Dialogue | Speaker-specific social register, cadence, `ты/вы`, and relationship. |
| Design or lore note | Clear analytical Russian without office jargon or loss of the underlying concept. |
| Letter, verse, riddle, prop | Preserve function and speaker; transcreate only what cannot survive literally. |

Classical gothic prose is a touchstone for restraint, rhythm, and a living educated voice—not a template to imitate. Do not make all narration comma-heavy, archaic, solemn, or uniformly ominous.

For atmospheric prose, identify the source-supported dominant effect—dread, grief, oppression, decay, isolation, black humor, tenderness, or another note—and preserve that effect. Do not replace it with generic gothic mood.

## Diagnose calques contextually

Treat a watchlist match as a question, never an automatic substitution. Determine the source sense and target register before changing anything. A familiar expression may be idiomatic in one context and translation-shaped in another.

High-value diagnostic questions:

- Is a bureaucratic copula or abstract noun hiding a simpler verb?
- Did an English passive introduce clumsy Russian, or does the passive focus matter?
- Did a purpose clause become abstract padding such as `для создания … опыта`?
- Did an English invitation become `чувствуйте себя свободно` instead of `можете` or `не стесняйтесь`?
- Does a standard phrase such as `держите в уме` fit this instruction's register, or would `помните` or `не забывайте` be more direct? Do not call the idiom a calque merely because it resembles English.
- Did workplace or gaming slang replace a precise Russian word without being an approved game term or deliberate voice choice?
- Did repeated `что`/`который`, participles, or gerunds create a sentence a native editor would naturally split?

Never ban ordinary words such as `момент`, `убедиться`, `столкнуться`, or passive constructions wholesale. Never replace a flagged expression without checking actor, mechanics, imagery, and register.

## Preserve gothic restraint

Choose among Russian synonyms only when they denote the same fact at the same intensity. These are not interchangeable by atmosphere alone:

- `старый`, `ветхий`, `древний`, and `дряхлый` imply different age or condition;
- `туман`, `мгла`, `марево`, and `пелена` describe different phenomena or images;
- `дом`, `изба`, `хижина`, and `особняк` change architecture and social status;
- `идти`, `брести`, and `тащиться` change manner;
- `сказать`, `прошептать`, and `выдавить` change delivery.

Do not invent a concrete detail to replace a generic adjective. Do not use a stronger synonym merely because it sounds gothic. Preserve deliberate plainness.

## Edit surgically

Fix the smallest span that resolves the defect. Preserve already-natural adjacent Russian unless source correspondence, voice, terminology, or continuity requires a wider rewrite. A stylistic pass must not become an untracked retranscreation.

Read the Russian target once without looking at the source. Mark stumbling rhythm, ambiguous pronouns, accidental comedy, repetitive syntax, and unnatural collocations. Then compare against the source and correct only changes that preserve fidelity.

Read every player-facing paragraph aloud. Rework a sentence if breath, stress, or word order exposes an English skeleton, but retain purposeful fragments, repetition, and awkwardness that belongs to the speaker.

## Use the living style watch

`.translation/ru/style-watch.tsv` stores reviewed recurring warning patterns. Only `approved` rows are scanned. A match does not fail QA and does not authorize automatic replacement.

Before a passing Russian-style review:

1. revise a genuine defect and rerun QA so the occurrence disappears; or
2. disposition the current occurrence as `accepted-context` or `false-positive` with a specific reason.

Record new observations as `candidate`. Promote, reject, or defer them only with sentence-level evidence and independent review. Never learn a pattern merely because a draft or scanner produced it.

The initial pre-translation baseline has one narrow bootstrap exception: an exact, high-signal literal may be approved after comparative review of a sealed raw reference or a repository-recorded excerpt and source hash, plus an independent forward/editorial check. Record that exception and its provenance explicitly. Once translation begins, new promotions require an actual pinned source/target sentence from a lifecycle unit; prescriptive lists alone are insufficient.

## Final native-ear check

- Russian syntax no longer shadows the English unnecessarily.
- Meaning, agency, mechanics, imagery, and certainty remain unchanged.
- Register matches the source passage and speaker.
- No generic gothic inflation, office prose, pseudo-archaism, or unexplained Anglicism remains.
- Russian quotation, dash, `ё`, capitalization, and address conventions follow reviewed project authority.
- Every style-watch flag has a current, evidence-backed disposition.
