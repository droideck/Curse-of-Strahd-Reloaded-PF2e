# Technical Preservation Contract

## Atomic scope

Edit the original content path on a dedicated translation branch. Do not rename files, add `rus` copies, alter assets incidentally, or mix source-edition conversion with translation. The pinned source is D&D 5e with a 2014 baseline even though the repository directory name mentions PF2e; this contract authorizes translation, not ruleset conversion.

One completed unit may change:

- the unit itself;
- mechanically synchronized inbound heading links;
- its persistent segment plan/progress/ledger;
- its heading map, QA/review records, glossary decisions, and lessons.

Do not change unrelated prose. Use the pinned Git commit as source; never treat a partially translated worktree file as the English original.

## Exact protected material

Preserve byte-for-byte:

- raw HTML opening/closing tags, tag case, spacing, attributes, attribute quoting, classes, IDs, styles, URLs, and intentionally malformed tags;
- image/embed targets, filenames, paths, Markdown link destinations, HTML `href`/`src`, and Canvas IDs/geometry;
- Obsidian block IDs, footnote IDs, HTML comments, entities, inline/fenced code, macros, Foundry roll syntax, and template tokens;
- every digit string, signed modifier, range, percentage, date, page number, dice formula, formula order, and action glyph;
- source tabs, hard line breaks, and file encoding/EOL unless an approved migration says otherwise.

Examples that must remain exact include `<div class=description>`, `class="ciation"`, `<Em>`, `![[The Durst Family.png]]`, `@Check[flat|dc:15]`, `[[/r 1d20+5]]`, `2d6 + 8`, `^heinrichsdiscipline`, and `<span class="action">▶▶</span>`.

Do not repair source markup while translating. Compare against the baseline and prohibit new defects.

## Markdown structure

Preserve:

- heading level, order, count, and stable scene code such as `A2a.`;
- callout type, capitalization, nesting, fold marker, and blockquote depth;
- list indentation and marker type;
- Markdown/HTML table row and cell shape;
- emphasis meaning and delimiter balance;
- paragraph order, block order, blank structural quote lines, and thematic breaks;
- statblock, read-aloud, citation, credit, highlight, sidebar, and flowchart containers.

Keep a whole table, raw-HTML statblock, code block, read-aloud container, letter, poem, or dialogue exchange in one translation segment. Keep ordinary callouts whole. If a callout alone exceeds the configured context limit, split it only at a planner-approved quote-only paragraph or list-item boundary and carry the exact blockquote/list prefix and heading context into the continuation.

## Headings and Obsidian links

Keep filenames stable. Translate heading text but retain its scene code. Align source and Russian headings by ordinal only when levels and stable codes match.

Run `sync-links` after heading translation. It must:

1. record source heading → Russian heading for the unit;
2. update self-links and every inbound `#heading` component across content files;
3. preserve the destination filename and block IDs;
4. preserve an English display alias in an untranslated file when necessary;
5. translate visible aliases during that file's own translation;
6. reject ambiguous duplicate headings or unresolved new targets.
7. move any previously completed inbound unit changed by the generated rewrite to `consistency_review` until `revalidate-links` verifies the exact generated hash, deterministic QA, and navigation notes from an independent reviewer.

Before item 7 writes a completed inbound unit, compare the prospective structured style-watch fingerprint with its reviewed report. Abort atomically on a difference. A coordinator may explicitly acknowledge a reviewed prospective delta with a nonempty reason, but final completion still requires the separate identity-bound Russian-style delta reviewer; the acknowledgement itself is never approval.

Use no-regression link validation because the source already contains historical irregularities.

## Evidence identity and workflow seal

Written QA and both independent reviews are identity-bound to the pinned source blob, current target hash, workflow hashes, and the authority hashes for `glossary.tsv`, `style-watch.tsv`, `style-guide.md`, and `voice-cards.md`. Editing any authority file makes prior QA/review evidence stale. Generate a fresh written QA report and obtain fresh passes from both required review roles; retaining one review from the old authority snapshot is not sufficient.

Treat translation state as reviewed data, not informal scratch files. `config.json`, its seal, `manifest.json`, `heading-map.json`, all four TSV registers, and the Markdown authority/memory files must be regular, non-symlink files with mode `0644`. Preserve the exact ordered TSV headers defined by the initialized templates; use tab delimiters, unique source keys/issue IDs, canonical lifecycle statuses, and complete provenance fields. `status` and every mutation gate must reject a malformed schema, duplicate key, missing decision evidence, symlink, or mode drift rather than silently treating the affected register as empty.

`style-watch.tsv` may contain literal surface forms only, never executable regular expressions. Only reviewed `approved` rows produce QA flags. Matches are contextual warnings rather than automatic replacements or hard failures. A passing Russian-style review must cover every current occurrence key exactly once; a failing review may identify a genuine flagged defect without misclassifying it. Fixing the prose requires fresh QA, while retaining a match in a passing target requires a specific `accepted-context` or `false-positive` disposition.

When navigation-only `revalidate-links` changes the Russian-reviewed style-watch fingerprint, the navigation reviewer cannot approve the linguistic delta alone. Completion requires a distinct reviewer, independent from both translators, with nonempty style notes and exact identity-bound dispositions for every current flag. Persist and revalidate the semantic fingerprint, current fingerprint, target hash, dispositions, and both reviewer identities. A genuine defect must be revised and resynchronized, never labeled as an acceptable exception.

Workflow-support files are separately protected by the reviewed seal checked by `status`. Change and review them only between units, then run `seal-workflow --reason "..."`. The command requires the existing config seal and fixed quality-gate contract to remain valid: it may approve support drift, never unrelated config edits or weakened review gates. Resealing records support identity; it neither approves content nor replaces deterministic QA, segment completion, independent review, or learning gates.

Semantic revision of a completed unit must use `reopen`, never a manual status edit. The command requires the prior target/evidence to be committed and valid, archives that completion, records the revision trigger, and restarts every content gate against the pinned English source. Navigation-only generated anchor changes continue to use `consistency_review`/`revalidate-links` instead.

## Visible versus technical text

Translate visible prose, headings, callout titles, link aliases, table labels, statblock labels/text, and safe Canvas text/edge labels.

Do not translate HTML attributes, path-like text, code-like tokens, raw link destinations, CSS class names, IDs, formulas, or machine keys. A visible game abbreviation may change only through an approved glossary mapping.

For YAML, preserve delimiters, keys, order, quoting, and nonprose values. Translate only allowlisted prose fields such as `description`, `keywords`, `title`, or `aliases`, as configured.

For Canvas JSON, permit only `nodes[*].text` and `edges[*].label` string changes. Preserve object/array topology and key order, IDs, node types, coordinates, sizes, colors, endpoints, and valid JSON escaping.

## Mechanical invariants

Preserve actor and target, negation, optional/mandatory modality, trigger, timing, success/failure branch, frequency, duration, range, direction, quantity, damage, healing, AC/DC/HP values, advantage/disadvantage, action economy, and resource cost.

Automated numeric parity is necessary but insufficient. An independent fidelity reviewer must check every rule, conditional, statblock, table, and repeated feature.

## Source defects and exceptions

Translate obvious prose typos naturally in visible Russian. Do not modify the English source or technical markup as part of that correction. Record uncertain lore/mechanical defects instead of guessing.

Any QA exception must be narrow and fingerprinted by rule, path, source-context hash, reason, and reviewer. Reject stale exceptions. Never use a file-wide exception to hide drift.

## Raster assets

Raster assets are outside the Markdown/Canvas unit state machine. Consequently, text-unit `completed` is not a publication-readiness certificate. Use `.translation/ru/visual-assets.json` as the pinned-source inventory of every embedded local raster and any explicitly retained supplemental candidate. `needs-text-audit` is not permission to skip an image; classify it before its embedding unit is considered publication-ready.

For confirmed text-bearing images, preserve pixel dimensions, format, filename references, composition, legibility, and setting-appropriate typography. Keep the untouched source blob available through Git. Require source-text transcription, OCR/manual parity, Russian proofreading, side-by-side visual comparison, and verification in every path listed in `embedded_by`. Record the visual checklist result in the inventory; do not represent the raster as a lifecycle unit or pass it through text-unit commands.
