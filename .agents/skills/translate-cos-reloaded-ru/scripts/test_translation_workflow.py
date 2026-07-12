#!/usr/bin/env python3

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


sys.dont_write_bytecode = True
SCRIPT = Path(__file__).with_name("translation_workflow.py")
SPEC = importlib.util.spec_from_file_location("translation_workflow", SCRIPT)
assert SPEC and SPEC.loader
workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow)


class MarkdownContractTests(unittest.TestCase):
    def setUp(self):
        self.source = """# A1. The Gate
> [!Warning]+ **Read This**
> If the players cross the gate, read:
<div class=description style="content: 'a > b';">
<p>The gate opens on a DC 15 check and deals 7 (2d6 + 3) damage.</p>
</div>
See [[#A1. The Gate|the gate]] and ![[Gate.png]].
"""
        self.target = """# A1. Врата
> [!Warning]+ **Прочтите это**
> Если игроки пересекают врата, прочтите:
<div class=description style="content: 'a > b';">
<p>Врата открываются при проверке Сл 15 и наносят 7 (2d6 + 3) урона.</p>
</div>
См. [[#A1. Врата|врата]] и ![[Gate.png]].
"""
        self.maps = {"unit.md": {"A1. The Gate": "A1. Врата"}}

    def compare(self, target):
        return workflow.compare_markdown(
            self.source,
            target,
            current_path="unit.md",
            content_paths=["unit.md"],
            heading_maps=self.maps,
            minimum_cyrillic_ratio=0.20,
        )

    def test_valid_translation_passes(self):
        result = self.compare(self.target)
        self.assertTrue(result["pass"], result["errors"])

    def test_html_attribute_change_fails(self):
        target = self.target.replace("class=description", 'class="description"')
        result = self.compare(target)
        self.assertFalse(result["pass"])
        self.assertTrue(any("raw HTML tags" in issue for issue in result["errors"]))

    def test_formula_change_fails(self):
        target = self.target.replace("2d6 + 3", "2d8 + 3")
        result = self.compare(target)
        self.assertFalse(result["pass"])
        self.assertTrue(any("dice formulas" in issue or "numeric tokens" in issue for issue in result["errors"]))

    def test_callout_case_change_fails(self):
        target = self.target.replace("[!Warning]", "[!warning]")
        result = self.compare(target)
        self.assertFalse(result["pass"])
        self.assertTrue(any("callout" in issue for issue in result["errors"]))

    def test_bare_url_must_be_preserved_exactly(self):
        source = "# Reference\nVisit https://example.invalid/path?q=1#anchor for details.\n"
        target = "# Источник\nПодробности: https://example.invalid/path?q=1#anchor.\n"
        baseline = workflow.compare_markdown(
            source,
            target,
            current_path="reference.md",
            content_paths=["reference.md"],
            heading_maps={"reference.md": {"Reference": "Источник"}},
            minimum_cyrillic_ratio=0.20,
        )
        self.assertTrue(baseline["pass"], baseline["errors"])

        changed = target.replace("example.invalid", "mirror.invalid")
        result = workflow.compare_markdown(
            source,
            changed,
            current_path="reference.md",
            content_paths=["reference.md"],
            heading_maps={"reference.md": {"Reference": "Источник"}},
            minimum_cyrillic_ratio=0.20,
        )
        self.assertFalse(result["pass"])
        self.assertTrue(any("bare URLs" in issue for issue in result["errors"]), result["errors"])

    def test_arbitrary_inline_and_fenced_code_is_byte_stable(self):
        source = (
            "# Code Samples\n"
            "Use `` `literal` and [[Guide#Gate]] `` exactly.\n"
            "\n"
            "~~~json\n"
            '{"url":"https://example.invalid/a", "macro":"[[Guide#Gate]]"}\n'
            "~~~\n"
            "Continue after the example.\n"
        )
        target = (
            "# Примеры кода\n"
            "Используйте `` `literal` and [[Guide#Gate]] `` без изменений.\n"
            "\n"
            "~~~json\n"
            '{"url":"https://example.invalid/a", "macro":"[[Guide#Gate]]"}\n'
            "~~~\n"
            "Затем продолжайте.\n"
        )
        baseline = workflow.compare_markdown(
            source,
            target,
            current_path="code.md",
            content_paths=["code.md", "Guide.md"],
            heading_maps={"code.md": {"Code Samples": "Примеры кода"}},
            minimum_cyrillic_ratio=0.20,
        )
        self.assertTrue(baseline["pass"], baseline["errors"])

        changed = target.replace('"macro":"[[Guide#Gate]]"', '"macro":"[[Guide#Door]]"')
        result = workflow.compare_markdown(
            source,
            changed,
            current_path="code.md",
            content_paths=["code.md", "Guide.md"],
            heading_maps={"code.md": {"Code Samples": "Примеры кода"}},
            minimum_cyrillic_ratio=0.20,
        )
        self.assertFalse(result["pass"])
        self.assertTrue(any("code spans/blocks" in issue for issue in result["errors"]), result["errors"])

    def test_distinct_source_headings_cannot_collapse_to_one_target_anchor(self):
        result = workflow.compare_markdown(
            "# Gate\nThe gate opens.\n# Door\nThe door closes.\n",
            "# Врата\nВрата открываются.\n# Врата\nВрата закрываются.\n",
            current_path="collision.md",
            content_paths=["collision.md"],
            heading_maps={"collision.md": {"Gate": "Врата", "Door": "Врата"}},
            minimum_cyrillic_ratio=0.20,
        )
        self.assertFalse(result["pass"])
        self.assertTrue(any("collapse" in issue for issue in result["errors"]), result["errors"])


class LinkRewriteTests(unittest.TestCase):
    def test_inbound_link_gets_stable_target_and_source_alias(self):
        index = workflow.wiki_file_index(["A.md", "B.md"])
        translated, problems = workflow.rewrite_links_for_unit(
            "See [[A#A1. The Gate]].\n",
            current_path="B.md",
            target_path="A.md",
            index=index,
            mapping={"A1. The Gate": "A1. Врата"},
            preserve_english_display=True,
        )
        self.assertFalse(problems)
        self.assertEqual(translated, "See [[A#A1. Врата|A1. The Gate]].\n")

    def test_protected_macro_is_not_visible_to_language_or_glossary_checks(self):
        visible = workflow.visible_text("Пройдите @Check[flat|dc:15], затем продолжайте.")
        self.assertNotIn("flat", visible)
        self.assertNotIn("dc", visible.casefold())

    def test_atomic_write_preserves_existing_file_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unit.md"
            path.write_text("source", encoding="utf-8")
            os.chmod(path, 0o644)
            workflow.atomic_write_bytes(path, "перевод".encode("utf-8"))
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_link_rewrite_skips_multibacktick_and_fenced_code(self):
        source = (
            "See [[A#Gate]].\n"
            "``Keep [[A#Gate]] literal``\n"
            "~~~text\n"
            "Keep [[A#Gate]] literal\n"
            "~~~\n"
        )
        translated, problems = workflow.rewrite_links_for_unit(
            source,
            current_path="B.md",
            target_path="A.md",
            index=workflow.wiki_file_index(["A.md", "B.md"]),
            mapping={"Gate": "Врата"},
            preserve_english_display=True,
        )
        self.assertFalse(problems)
        self.assertIn("See [[A#Врата|Gate]].", translated)
        self.assertIn("``Keep [[A#Gate]] literal``", translated)
        self.assertIn("~~~text\nKeep [[A#Gate]] literal\n~~~", translated)

    def test_commonmark_multiline_code_and_longer_closing_fence_are_protected(self):
        source = (
            "``inline code may\ncontain [[A#Gate]] on two lines``\n"
            "```text\n[[A#Gate]]\n````\n"
            "Visible [[A#Gate]].\n"
        )
        translated, problems = workflow.rewrite_links_for_unit(
            source,
            current_path="B.md",
            target_path="A.md",
            index=workflow.wiki_file_index(["A.md", "B.md"]),
            mapping={"Gate": "Врата"},
            preserve_english_display=False,
        )
        self.assertFalse(problems)
        self.assertIn("contain [[A#Gate]] on two lines", translated)
        self.assertIn("```text\n[[A#Gate]]\n````", translated)
        self.assertIn("Visible [[A#Врата]].", translated)

    def test_canvas_rewrite_only_touches_allowlisted_schema_fields(self):
        payload = {
            "nodes": [{"id": "n", "type": "text", "text": "[[A#Gate]]"}],
            "edges": [],
            "metadata": {"label": "[[A#Gate]]", "text": "[[A#Gate]]"},
        }
        rewritten, problems = workflow.rewrite_canvas_links_for_unit(
            json.dumps(payload),
            current_path="Map.canvas",
            target_path="A.md",
            index=workflow.wiki_file_index(["A.md", "Map.canvas"]),
            mapping={"Gate": "Врата"},
            preserve_english_display=False,
        )
        self.assertFalse(problems)
        result = json.loads(rewritten)
        self.assertEqual(result["nodes"][0]["text"], "[[A#Врата]]")
        self.assertEqual(result["metadata"]["label"], "[[A#Gate]]")
        self.assertEqual(result["metadata"]["text"], "[[A#Gate]]")

    def test_blockquoted_indented_and_unclosed_protected_regions_are_not_rewritten(self):
        source = (
            "> ```text\n> [[A#Gate]]\n> ````\n"
            "\n    [[A#Gate]]\n"
            "<!-- unclosed [[A#Gate]]"
        )
        translated, problems = workflow.rewrite_links_for_unit(
            source,
            current_path="B.md",
            target_path="A.md",
            index=workflow.wiki_file_index(["A.md", "B.md"]),
            mapping={"Gate": "Врата"},
            preserve_english_display=False,
        )
        self.assertFalse(problems)
        self.assertEqual(translated, source)

    def test_balanced_closing_parenthesis_is_part_of_a_bare_url(self):
        source = "См. https://example.invalid/wiki/Thing_(bar)\n"
        target = "См. https://example.invalid/wiki/Thing_(bar\n"
        result = workflow.compare_markdown(
            source,
            target,
            current_path="url.md",
            content_paths=["url.md"],
            heading_maps={},
            minimum_cyrillic_ratio=0.20,
        )
        self.assertFalse(result["pass"])
        self.assertTrue(any("bare URLs" in issue for issue in result["errors"]), result["errors"])


class HistoricalQuirkTests(unittest.TestCase):
    def setUp(self):
        self.source = """# S1. Broken Markup
<span class="ciation"><Em>See page 2.</Em></span>
> [!info]+ **A Note**
> Read the old oath.[^oath]
> ^old-oath
See [[#^old-oath|the oath]] and [the source](https://example.invalid/a).
| Result | Effect
|---|---
| 1 | Nothing happens.
[^oath]: The oath remains binding for 3 days.
A +4 result changes the 1-2 range by 10%.
"""
        self.target = """# S1. Повреждённая разметка
<span class="ciation"><Em>См. страницу 2.</Em></span>
> [!info]+ **Примечание**
> Прочтите старую клятву.[^oath]
> ^old-oath
См. [[#^old-oath|клятву]] и [источник](https://example.invalid/a).
| Результат | Эффект
|---|---
| 1 | Ничего не происходит.
[^oath]: Клятва остаётся в силе 3 дня.
Результат +4 изменяет диапазон 1-2 на 10%.
"""

    def compare(self, target):
        return workflow.compare_markdown(
            self.source,
            target,
            current_path="quirk.md",
            content_paths=["quirk.md"],
            heading_maps={"quirk.md": {"S1. Broken Markup": "S1. Повреждённая разметка"}},
            minimum_cyrillic_ratio=0.20,
        )

    def test_historical_quirks_pass_when_preserved(self):
        result = self.compare(self.target)
        self.assertTrue(result["pass"], result["errors"])

    def test_block_id_change_fails(self):
        result = self.compare(self.target.replace("^old-oath", "^old-vow"))
        self.assertFalse(result["pass"])
        self.assertTrue(any("block id" in issue for issue in result["errors"]))

    def test_external_destination_change_fails(self):
        result = self.compare(self.target.replace("example.invalid/a", "example.invalid/b"))
        self.assertFalse(result["pass"])
        self.assertTrue(any("destinations" in issue for issue in result["errors"]))

    def test_source_table_quirk_cannot_be_repaired(self):
        result = self.compare(self.target.replace("| Результат | Эффект", "| Результат | Эффект |"))
        self.assertFalse(result["pass"])
        self.assertTrue(any("table pipe" in issue for issue in result["errors"]))

    def test_signed_modifier_change_fails_even_when_digits_match(self):
        result = self.compare(self.target.replace("Результат +4", "Результат -4"))
        self.assertFalse(result["pass"])
        self.assertTrue(any("signed modifiers" in issue for issue in result["errors"]))


class FrontmatterContractTests(unittest.TestCase):
    def test_translatable_yaml_value_keeps_quoting_style(self):
        source = "---\ncover: preview.png\ndescription: A dark valley.\n---\n# Guide\nRead this guide.\n"
        target = "---\ncover: preview.png\ndescription: Тёмная долина.\n---\n# Руководство\nПрочтите это руководство.\n"
        result = workflow.compare_markdown(
            source,
            target,
            current_path="guide.md",
            content_paths=["guide.md"],
            heading_maps={"guide.md": {"Guide": "Руководство"}},
            yaml_allow_keys={"description"},
            minimum_cyrillic_ratio=0.20,
        )
        self.assertTrue(result["pass"], result["errors"])
        changed = target.replace("description: Тёмная долина.", 'description: "Тёмная долина."')
        result = workflow.compare_markdown(
            source,
            changed,
            current_path="guide.md",
            content_paths=["guide.md"],
            heading_maps={"guide.md": {"Guide": "Руководство"}},
            yaml_allow_keys={"description"},
            minimum_cyrillic_ratio=0.20,
        )
        self.assertFalse(result["pass"])
        self.assertTrue(any("YAML" in issue for issue in result["errors"]))

    def test_unchanged_short_heading_is_a_hard_failure(self):
        result = workflow.compare_markdown(
            "# Actions\nThe creature attacks.\n",
            "# Actions\nСущество атакует.\n",
            current_path="statblock.md",
            content_paths=["statblock.md"],
            heading_maps={"statblock.md": {"Actions": "Actions"}},
            minimum_cyrillic_ratio=0.20,
        )
        self.assertFalse(result["pass"])
        self.assertTrue(any("appears unchanged" in issue for issue in result["errors"]))

    def test_unchanged_html_statblock_heading_is_a_hard_failure(self):
        result = workflow.compare_markdown(
            "<h3>Actions</h3>\n<p>The creature attacks.</p>\n",
            "<h3>Actions</h3>\n<p>Существо атакует.</p>\n",
            current_path="statblock.md",
            content_paths=["statblock.md"],
            heading_maps={},
            minimum_cyrillic_ratio=0.20,
        )
        self.assertFalse(result["pass"])
        self.assertTrue(any("appears unchanged" in issue for issue in result["errors"]))


class CanvasContractTests(unittest.TestCase):
    def setUp(self):
        self.source_payload = {
            "nodes": [{"id": "n1", "type": "text", "text": "The road is 2 miles long.", "x": 10, "y": 20}],
            "edges": [{"id": "e1", "fromNode": "n1", "toNode": "n1", "label": "Return"}],
        }

    def test_only_visible_canvas_text_may_change(self):
        target = json.loads(json.dumps(self.source_payload))
        target["nodes"][0]["text"] = "Дорога имеет длину 2 мили."
        target["edges"][0]["label"] = "Вернуться"
        result = workflow.compare_canvas(
            json.dumps(self.source_payload), json.dumps(target, ensure_ascii=False), minimum_cyrillic_ratio=0.20
        )
        self.assertTrue(result["pass"], result["errors"])

    def test_canvas_geometry_change_fails(self):
        target = json.loads(json.dumps(self.source_payload))
        target["nodes"][0]["text"] = "Дорога имеет длину 2 мили."
        target["edges"][0]["label"] = "Вернуться"
        target["nodes"][0]["x"] = 11
        result = workflow.compare_canvas(
            json.dumps(self.source_payload), json.dumps(target, ensure_ascii=False), minimum_cyrillic_ratio=0.20
        )
        self.assertFalse(result["pass"])
        self.assertTrue(any("protected Canvas value" in issue for issue in result["errors"]))

    def test_canvas_visible_text_still_protects_markup_macros_and_formulas(self):
        source = json.loads(json.dumps(self.source_payload))
        source["nodes"][0]["text"] = (
            '<span class="roll">Roll 2d6 with @Check[flat|dc:15] and '
            '[read this](https://example.invalid/a).</span>'
        )
        target = json.loads(json.dumps(source))
        target["nodes"][0]["text"] = (
            '<span class="roll">Бросьте 2d6 с @Check[flat|dc:15] и '
            '[прочтите это](https://example.invalid/a).</span>'
        )
        target["edges"][0]["label"] = "Вернуться"
        baseline = workflow.compare_canvas(
            json.dumps(source), json.dumps(target, ensure_ascii=False), minimum_cyrillic_ratio=0.20
        )
        self.assertTrue(baseline["pass"], baseline["errors"])
        mutations = [
            ("2d6", "2d8"),
            ("dc:15", "dc:16"),
            ("example.invalid/a", "example.invalid/b"),
            ('class=\\"roll\\"', 'class=\\"changed\\"'),
        ]
        serialized = json.dumps(target, ensure_ascii=False)
        for old, new in mutations:
            with self.subTest(old=old):
                changed = serialized.replace(old, new)
                result = workflow.compare_canvas(json.dumps(source), changed, minimum_cyrillic_ratio=0.20)
                self.assertFalse(result["pass"], result)

    def test_canvas_wikilink_accepts_the_mapped_russian_heading(self):
        source = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "text",
                    "text": "Travel to [[Guide#The Gate|the gate]].",
                    "x": 10,
                    "y": 20,
                }
            ],
            "edges": [],
        }
        target = json.loads(json.dumps(source))
        target["nodes"][0]["text"] = "Идите к [[Guide#Врата|вратам]]."
        result = workflow.compare_canvas(
            json.dumps(source),
            json.dumps(target, ensure_ascii=False),
            minimum_cyrillic_ratio=0.20,
            current_path="Map.canvas",
            content_paths=["Map.canvas", "Guide.md"],
            heading_maps={"Guide.md": {"The Gate": "Врата"}},
        )
        self.assertTrue(result["pass"], result["errors"])

        target["nodes"][0]["text"] = "Идите к [[Guide#The Gate|вратам]]."
        stale = workflow.compare_canvas(
            json.dumps(source),
            json.dumps(target, ensure_ascii=False),
            minimum_cyrillic_ratio=0.20,
            current_path="Map.canvas",
            content_paths=["Map.canvas", "Guide.md"],
            heading_maps={"Guide.md": {"The Gate": "Врата"}},
        )
        self.assertFalse(stale["pass"])
        self.assertTrue(any("not mapped" in issue for issue in stale["errors"]), stale["errors"])

    def test_canvas_reformatting_outside_allowlisted_strings_fails(self):
        target = json.loads(json.dumps(self.source_payload))
        target["nodes"][0]["text"] = "Дорога имеет длину 2 мили."
        target["edges"][0]["label"] = "Вернуться"
        source = json.dumps(self.source_payload, separators=(",", ":"))
        reformatted = json.dumps(target, ensure_ascii=False, indent=2)
        result = workflow.compare_canvas(source, reformatted, minimum_cyrillic_ratio=0.20)
        self.assertFalse(result["pass"])
        self.assertTrue(any("raw JSON bytes" in issue for issue in result["errors"]), result["errors"])


class SegmentPlanningTests(unittest.TestCase):
    def test_small_callout_is_not_split_when_its_heading_section_is_large(self):
        text = (
            "# Large Section\n"
            + "Outside prose words repeated for context. " * 12
            + "\n\n> [!info]+ **Small Callout**\n> First short paragraph.\n>\n> - One item.\n> - Two items.\n\n"
            + "Closing prose words repeated. " * 8
        )
        plan = workflow.segment_plan(text, 30)
        lines = text.splitlines()
        callout_start = next(index for index, line in enumerate(lines) if "[!info]" in line)
        callout_end = callout_start + 1
        while callout_end < len(lines) and (not lines[callout_end].strip() or lines[callout_end].lstrip().startswith(">")):
            callout_end += 1
        starts = {item["start_line"] - 1 for item in plan}
        self.assertFalse(any(callout_start < start < callout_end for start in starts), plan)

    def test_mixed_eol_sequence_hash_detects_line_assignment_changes(self):
        first = workflow.source_format(b"one\r\ntwo\n")
        second = workflow.source_format(b"one\ntwo\r\n")
        self.assertEqual(first["eol"], "mixed")
        self.assertEqual(second["eol"], "mixed")
        self.assertNotEqual(first["eol_sequence_sha256"], second["eol_sequence_sha256"])


class LinkResolutionTests(unittest.TestCase):
    def test_missing_manifest_target_is_not_treated_as_present(self):
        issues = workflow.link_issue_set(
            {"A.md": "See [[B]].\n"},
            ["A.md", "B.md"],
        )
        self.assertTrue(any("unresolved-file:B" in issue for issue in issues), issues)

    def test_canvas_visible_text_participates_in_broken_link_scan(self):
        canvas = {
            "nodes": [{"id": "n1", "type": "text", "text": "Follow [[Missing Guide#Gate]]."}],
            "edges": [{"id": "e1", "fromNode": "n1", "toNode": "n1", "label": "[[Also Missing]]"}],
        }
        issues = workflow.link_issue_set(
            {"Map.canvas": json.dumps(canvas)},
            ["Map.canvas", "Guide.md"],
        )
        self.assertTrue(any("$.nodes[0].text:unresolved-file:Missing Guide" in issue for issue in issues), issues)
        self.assertTrue(any("$.edges[0].label:unresolved-file:Also Missing" in issue for issue in issues), issues)


class GlossaryContractTests(unittest.TestCase):
    def test_enforced_source_term_requires_an_approved_russian_form_on_that_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / workflow.STATE_REL
            state.mkdir(parents=True)
            (state / "glossary.tsv").write_text(
                "source\tapproved_ru\tforms\tstatus\tenforce\tforbidden_variants\tnotes\n"
                "Strahd\tСтрад\tСтрада;Страду\tapproved\tyes\t\tcanonical name\n",
                encoding="utf-8",
            )
            source = "Strahd enters the hall.\n"
            errors, _ = workflow.glossary_issues(root, source, "Страд входит в зал.\n")
            self.assertFalse(errors, errors)
            inflected_errors, _ = workflow.glossary_issues(root, source, "В зале ждут Страда.\n")
            self.assertFalse(inflected_errors, inflected_errors)

            wrong_errors, _ = workflow.glossary_issues(root, source, "Граф входит в зал.\n")
            self.assertTrue(any("approved Russian form missing" in issue for issue in wrong_errors), wrong_errors)

    def test_capitalized_named_term_does_not_match_generic_lowercase_word(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / workflow.STATE_REL
            state.mkdir(parents=True)
            (state / "glossary.tsv").write_text(
                "source\tapproved_ru\tforms\tcapitalization\tstatus\tenforce\tforbidden_variants\tnotes\n"
                "Mists\tТуманы\tТуманах\tcapitalized\tapproved\tyes\t\tnamed phenomenon only\n",
                encoding="utf-8",
            )
            errors, _ = workflow.glossary_issues(
                root,
                "Their breath mists in the cold.\n",
                "На холоде их дыхание клубится паром.\n",
            )
            self.assertFalse(errors)


class StyleWatchTests(unittest.TestCase):
    def write_watch(self, root: Path, rows: list[dict[str, str]]) -> None:
        state = root / workflow.STATE_REL
        state.mkdir(parents=True, exist_ok=True)
        lines = ["\t".join(workflow.STYLE_WATCH_HEADER)]
        lines.extend("\t".join(row.get(name, "") for name in workflow.STYLE_WATCH_HEADER) for row in rows)
        (state / workflow.STYLE_WATCH_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_approved_literals_use_unicode_boundaries_and_mask_protected_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_watch(
                root,
                [
                    {
                        "id": "RUQ-900",
                        "status": "approved",
                        "literals": "данный",
                        "category": "test",
                        "guidance": "Review the visible standalone form.",
                        "applicability": "Visible prose.",
                        "exceptions": "Document an intentional use.",
                        "evidence": "test evidence",
                        "origin_unit": "test-unit",
                        "reviewer": "reviewer",
                        "decision_date": "2026-07-12",
                    },
                    {
                        "id": "RUQ-901",
                        "status": "candidate",
                        "literals": "локация",
                        "category": "test-candidate",
                        "guidance": "Candidate rows must not scan.",
                        "applicability": "Visible prose.",
                        "exceptions": "Not applicable until approved.",
                        "evidence": "test evidence",
                        "origin_unit": "test-unit",
                    },
                ],
            )
            markdown = (
                "Переданный свиток лежит рядом.\n"
                "Данный свиток лежит рядом с локацией.\n"
                "`Данный` <!-- Данный --> @Check[Данный] <span title=\"Данный\">Чисто</span> ![[Данный.png]]\n"
                "См. [[Guide|Данный]].\n"
            )
            findings = workflow.style_watch_findings(
                root,
                [("", markdown), ("$.nodes[0].text", "Данный выбор остаётся за вами.")],
            )
            self.assertEqual(len(findings), 3, findings)
            self.assertEqual({item["rule_id"] for item in findings}, {"RUQ-900"})
            self.assertEqual(
                {item["location"] for item in findings},
                {"line 2", "line 4", "$.nodes[0].text:line 1"},
            )

    def test_style_flag_fingerprint_detects_report_tampering(self):
        flags = [
            {
                "key": "RUQ-900:abc",
                "rule_id": "RUQ-900",
                "location": "line 2",
                "literal": "Данный",
                "category": "test",
                "guidance": "Review it.",
                "applicability": "Visible prose.",
                "exceptions": "Intentional speech.",
                "excerpt": "Данный свиток.",
            }
        ]
        report = {"style_flags": flags, "style_flags_sha256": workflow.style_flags_fingerprint(flags)}
        self.assertEqual(workflow.validate_style_flags_report(report), flags)
        report["style_flags"][0]["excerpt"] = "Tampered"
        with self.assertRaises(workflow.WorkflowError):
            workflow.validate_style_flags_report(report)


class TemporaryGitWorkflowTests(unittest.TestCase):
    """Exercise CLI commands and persisted state in a real, isolated Git repo."""

    ARC_A = "Act I - Into the Mists/Arc A - Escape From Death House.md"
    ARC_B = "Act I - Into the Mists/Arc B - Welcome to Barovia.md"
    GUIDE = "Introduction/Using This Guide.md"
    SOURCE_A = "# A1. The Gate\nThe players enter Death House.\n"
    TARGET_A = "# A1. Врата\nГерои входят в Дом Смерти.\n"
    SOURCE_LINK = "[[Arc A - Escape From Death House#A1. The Gate|the gate]]"

    def setUp(self):
        self.previous_cwd = Path.cwd()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self._git("init", "-b", "codex/test")
        self._git("config", "user.name", "Workflow Test")
        self._git("config", "user.email", "workflow-test@example.invalid")

        (self.root / self.ARC_A).parent.mkdir(parents=True, exist_ok=True)
        (self.root / self.GUIDE).parent.mkdir(parents=True, exist_ok=True)
        (self.root / self.ARC_A).write_text(self.SOURCE_A, encoding="utf-8")
        (self.root / self.ARC_B).write_text(
            "# B1. Arrival\n"
            f"See {self.SOURCE_LINK}.\n"
            f"`{self.SOURCE_LINK}`\n"
            f"<!-- {self.SOURCE_LINK} -->\n",
            encoding="utf-8",
        )
        (self.root / self.GUIDE).write_text(
            "# Using This Guide\nThis guide uses the 2014 Rules.\n",
            encoding="utf-8",
        )

        # Production commands hash the skill implementation.  Copy it into the
        # fixture so those hashes are meaningful instead of a collection of
        # synthetic "missing" values.
        fixture_skill = self.root / workflow.SKILL_REL
        shutil.copytree(SCRIPT.parent.parent, fixture_skill)
        self._git("add", ".")
        self._git("commit", "-m", "fixture source")
        self.source_commit = self._git("rev-parse", "HEAD").stdout.strip()

        os.chdir(self.root)
        return_code, _, error = self.invoke("init", "--source-ref", "HEAD")
        self.assertEqual(return_code, 0, error)
        state = self.root / workflow.STATE_REL
        (state / "glossary.tsv").write_text(
            "\t".join(workflow.GLOSSARY_HEADER) + "\n",
            encoding="utf-8",
        )
        (state / "term-candidates.tsv").write_text(
            "\t".join(workflow.TERM_CANDIDATES_HEADER) + "\n", encoding="utf-8"
        )
        (state / workflow.STYLE_WATCH_NAME).write_text(
            "\t".join(workflow.STYLE_WATCH_HEADER) + "\n", encoding="utf-8"
        )
        (state / "source-issues.tsv").write_text(
            "\t".join(workflow.SOURCE_ISSUES_HEADER) + "\n", encoding="utf-8"
        )
        (state / "style-guide.md").write_text("# Style\n\nBaseline.\n", encoding="utf-8")
        (state / "voice-cards.md").write_text("# Voices\n\nBaseline.\n", encoding="utf-8")
        (state / "lessons.md").write_text("# Reviewed Translation Lessons\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self.previous_cwd)
        self.temporary_directory.cleanup()

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def invoke(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            return_code = workflow.main(list(arguments))
        return return_code, stdout.getvalue(), stderr.getvalue()

    def load_manifest(self) -> dict:
        return json.loads(
            (self.root / workflow.STATE_REL / workflow.MANIFEST_NAME).read_text(encoding="utf-8")
        )

    def unit(self, unit_id: str) -> dict:
        return next(item for item in self.load_manifest()["units"] if item["id"] == unit_id)

    def start_arc_a(self) -> None:
        return_code, _, error = self.invoke("start", "arc-a", "--translator", "translator-a")
        self.assertEqual(return_code, 0, error)

    def record_test_completion(self, unit_id: str, translator: str) -> None:
        config, manifest = workflow.load_state(self.root)
        unit = next(item for item in manifest["units"] if item["id"] == unit_id)
        target_path = self.root / unit["path"]
        target_hash = workflow.sha256_bytes(target_path.read_bytes())
        style_flags = workflow.style_watch_findings(
            self.root, [("", target_path.read_text(encoding="utf-8"))]
        )
        work = self.root / workflow.STATE_REL / workflow.WORK_DIR / unit_id
        work.mkdir(parents=True, exist_ok=True)
        if not (work / "segments.json").exists():
            workflow.atomic_write_json(work / "segments.json", {"unit_id": unit_id, "segments": []})
        if not (work / "progress.json").exists():
            workflow.atomic_write_json(work / "progress.json", {"unit_id": unit_id, "segments": []})
        if not (work / "ledger.md").exists():
            workflow.atomic_write_text(work / "ledger.md", "# Reviewed synthetic ledger\n")
        unit.update(
            {
                "status": "completed",
                "translator": unit.get("translator") or translator,
                "started_at": unit.get("started_at") or workflow.utc_now(),
                "started_head": unit.get("started_head") or self._git("rev-parse", "HEAD").stdout.strip(),
                "started_config_sha256": unit.get("started_config_sha256")
                or workflow.sha256_bytes((self.root / workflow.STATE_REL / workflow.CONFIG_NAME).read_bytes()),
                "prestart_sha256": unit.get("prestart_sha256") or unit["source_sha256"],
                "initial_ledger_sha256": unit.get("initial_ledger_sha256") or ("0" * 64),
                "completed_at": workflow.utc_now(),
                "target_sha256": target_hash,
                "semantic_target_sha256": target_hash,
                "qa_report": (workflow.STATE_REL / workflow.REPORTS_DIR / f"{unit_id}.json").as_posix(),
                "completed_project_hashes": workflow.project_hashes(self.root),
                "completed_workflow_hashes": workflow.workflow_hashes(self.root),
                "completion_minimum_review_score": config["minimum_review_score"],
                "completed_work_hashes": workflow.unit_work_hashes(self.root, unit),
                "learning_recorded": True,
            }
        )
        report = {
            "schema_version": 1,
            "unit_id": unit_id,
            "path": unit["path"],
            "checked_at": workflow.utc_now(),
            "pass": True,
            "errors": [],
            "warnings": [],
            "source_commit": config["source_commit"],
            "source_sha256": unit["source_sha256"],
            "target_sha256": target_hash,
            "project_hashes": unit["completed_project_hashes"],
            "authority_hashes": workflow.authority_hashes(self.root),
            "workflow_hashes": unit["completed_workflow_hashes"],
            "style_flags": style_flags,
            "style_flags_sha256": workflow.style_flags_fingerprint(style_flags),
        }
        report_path = self.root / workflow.STATE_REL / workflow.REPORTS_DIR / f"{unit_id}.json"
        workflow.atomic_write_json(report_path, report)
        if unit["path"].endswith(".md"):
            source_value = workflow.source_text(self.root, config["source_commit"], unit["path"])
            target_value = (self.root / unit["path"]).read_text(encoding="utf-8")
            src_rows = workflow.heading_rows(source_value)
            dst_rows = workflow.heading_rows(target_value)
            mapping = workflow.validated_heading_mapping(src_rows, dst_rows)
            heading_path = self.root / workflow.STATE_REL / workflow.HEADING_MAP_NAME
            heading_state = json.loads(heading_path.read_text(encoding="utf-8"))
            heading_state.setdefault("files", {})[unit["path"]] = {
                "unit_id": unit_id,
                "source_commit": config["source_commit"],
                "source_heading_sha256": workflow.sha256_text("\n".join(row["plain"] for row in src_rows)),
                "target_heading_sha256": workflow.sha256_text("\n".join(row["plain"] for row in dst_rows)),
                "updated_at": workflow.utc_now(),
                "headings": mapping,
            }
            workflow.atomic_write_json(heading_path, heading_state)
        review_dir = self.root / workflow.STATE_REL / workflow.REVIEWS_DIR / unit_id
        identity = workflow.qa_identity(report)
        scores = {key: 5 for key in ("fidelity", "mechanics", "terminology", "language", "navigation", "typography")}
        for role, reviewer in (("fidelity", f"{unit_id}-fidelity"), ("russian-style", f"{unit_id}-style")):
            review = {
                    "schema_version": 1,
                    "unit_id": unit_id,
                    "path": unit["path"],
                    "role": role,
                    "reviewer": reviewer,
                    "reviewed_at": workflow.utc_now(),
                    "verdict": "pass",
                    "score": 100,
                    "category_scores": scores,
                    "unresolved_issues": 0,
                    "issue_counts": {"blocker": 0, "major": 0, "minor": 0},
                    "notes": "Synthetic completed-unit evidence for state-machine integration testing.",
                    **identity,
            }
            if role == "russian-style":
                review.update(
                    {
                        "style_flags_sha256": report["style_flags_sha256"],
                        "reviewed_style_flag_keys": sorted(flag["key"] for flag in style_flags),
                        "style_dispositions": sorted(
                            [
                                {
                                    "key": flag["key"],
                                    "decision": "accepted-context",
                                    "reason": "Synthetic fixture records the current visible occurrence.",
                                }
                                for flag in style_flags
                            ],
                            key=lambda item: item["key"],
                        ),
                    }
                )
            workflow.atomic_write_json(review_dir / f"{role}.json", review)
        workflow.atomic_write_json(
            review_dir / "learning.json",
            {
                "schema_version": 1,
                "unit_id": unit_id,
                "path": unit["path"],
                "curator": f"{unit_id}-curator",
                "recorded_at": workflow.utc_now(),
                "terms_reviewed": True,
                "style_watch_reviewed": True,
                "project_hashes": unit["completed_project_hashes"],
                "lesson": "Synthetic reviewed lesson for integration testing.",
                **identity,
            },
        )
        workflow.atomic_write_json(self.root / workflow.STATE_REL / workflow.MANIFEST_NAME, manifest)

    def mark_arc_b_completed(self) -> None:
        target = self.root / self.ARC_B
        target.write_text(
            "# B1. Прибытие\n"
            f"См. {self.SOURCE_LINK}.\n"
            f"`{self.SOURCE_LINK}`\n"
            f"<!-- {self.SOURCE_LINK} -->\n",
            encoding="utf-8",
        )
        self._git("add", self.ARC_B)
        self._git("commit", "-m", "completed inbound translation fixture")
        self.record_test_completion("arc-b", "translator-b")
        self._git("add", str(workflow.STATE_REL))
        self._git("commit", "-m", "completed inbound evidence fixture")

    def write_target_a(self, *, final_newline: bool = True) -> None:
        text = self.TARGET_A if final_newline else self.TARGET_A.rstrip("\n")
        (self.root / self.ARC_A).write_text(text, encoding="utf-8", newline="")

    def sync_arc_a(self) -> None:
        return_code, _, error = self.invoke("sync-links", "arc-a")
        self.assertEqual(return_code, 0, error)

    def record_review(
        self,
        role: str,
        reviewer: str,
        *,
        style_dispositions: Path | None = None,
        verdict: str = "pass",
    ) -> tuple[int, str, str]:
        notes = self.root / workflow.STATE_REL / workflow.WORK_DIR / "arc-a" / f"{role}-notes.txt"
        notes.parent.mkdir(parents=True, exist_ok=True)
        notes.write_text("Checked fidelity, mechanics, terminology, language, and links.", encoding="utf-8")
        arguments = [
            "review",
            "arc-a",
            "--role",
            role,
            "--reviewer",
            reviewer,
            "--fidelity",
            "5",
            "--mechanics",
            "5",
            "--terminology",
            "5",
            "--language",
            "5",
            "--navigation",
            "5",
            "--typography",
            "5",
            "--verdict",
            verdict,
            "--blockers",
            "0",
            "--majors",
            "0",
            "--minors",
            "0",
            "--notes-file",
            str(notes),
        ]
        if style_dispositions is not None:
            arguments.extend(["--style-dispositions-file", str(style_dispositions)])
        return self.invoke(*arguments)

    def test_protected_branch_allows_read_only_qa_but_not_report_write_or_start(self):
        self.start_arc_a()
        self.write_target_a()
        self.sync_arc_a()
        self._git("branch", "-m", "main")
        manifest_path = self.root / workflow.STATE_REL / workflow.MANIFEST_NAME
        manifest_before = manifest_path.read_bytes()
        report_path = self.root / workflow.STATE_REL / workflow.REPORTS_DIR / "arc-a.json"

        read_code, _, read_error = self.invoke("qa", "arc-a")
        self.assertEqual(read_code, 0, read_error)
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertFalse(report_path.exists())

        write_code, _, write_error = self.invoke("qa", "arc-a", "--write-report")
        self.assertEqual(write_code, 2)
        self.assertIn("protected branch", write_error)
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertFalse(report_path.exists())

        start_code, _, start_error = self.invoke("start", "arc-a", "--translator", "translator-a")
        self.assertEqual(start_code, 2)
        self.assertIn("protected branch", start_error)

    def test_start_marks_unit_stale_when_head_blob_drifted_from_manifest(self):
        changed_source = self.SOURCE_A.replace("Death House", "the old manor")
        (self.root / self.ARC_A).write_text(changed_source, encoding="utf-8")
        self._git("add", self.ARC_A)
        self._git("commit", "-m", "upstream source drift")

        return_code, _, error = self.invoke("start", "arc-a", "--translator", "translator-a")
        self.assertEqual(return_code, 2)
        self.assertIn("source", error.casefold())
        self.assertEqual(self.unit("arc-a")["status"], "stale_source")

    def test_start_and_status_reject_mode_only_head_drift(self):
        os.chmod(self.root / self.ARC_A, 0o755)
        self._git("add", self.ARC_A)
        self._git("commit", "-m", "mode-only source drift")

        status_code, status_output, status_error = self.invoke("status")
        self.assertEqual(status_code, 2, status_error)
        self.assertIn("mode drift", status_output)
        start_code, _, start_error = self.invoke("start", "arc-a", "--translator", "translator-a")
        self.assertEqual(start_code, 2)
        self.assertIn("mode", start_error)
        self.assertEqual(self.unit("arc-a")["status"], "stale_source")

    def test_qa_rejects_missing_final_newline_from_pinned_source_format(self):
        self.start_arc_a()
        self.write_target_a(final_newline=False)
        self.sync_arc_a()

        return_code, output, error = self.invoke("qa", "arc-a")
        self.assertEqual(return_code, 1, error)
        self.assertIn("newline", output.casefold())

    def test_qa_enforces_bom_eol_and_executable_mode_from_pinned_source(self):
        self.start_arc_a()
        self.write_target_a()
        self.sync_arc_a()
        config, manifest = workflow.load_state(self.root)
        unit = next(item for item in manifest["units"] if item["id"] == "arc-a")
        target_path = self.root / self.ARC_A

        baseline = workflow.qa_unit(self.root, config, manifest, unit)
        self.assertTrue(baseline["pass"], baseline["errors"])

        mutations = {
            "BOM": b"\xef\xbb\xbf" + self.TARGET_A.encode("utf-8"),
            "CRLF": self.TARGET_A.replace("\n", "\r\n").encode("utf-8"),
        }
        for label, data in mutations.items():
            with self.subTest(label=label):
                target_path.write_bytes(data)
                report = workflow.qa_unit(self.root, config, manifest, unit)
                self.assertFalse(report["pass"])
                self.assertTrue(any("byte format changed" in issue for issue in report["errors"]), report["errors"])

        target_path.write_bytes(self.TARGET_A.encode("utf-8"))
        os.chmod(target_path, 0o755)
        mode_report = workflow.qa_unit(self.root, config, manifest, unit)
        self.assertFalse(mode_report["pass"])
        self.assertTrue(any("file mode changed" in issue for issue in mode_report["errors"]), mode_report["errors"])
        os.chmod(target_path, 0o644)

    def test_qa_rejects_a_symlink_target_even_when_linked_bytes_match(self):
        self.start_arc_a()
        linked = self.root / "translated-target.md"
        linked.write_text(self.TARGET_A, encoding="utf-8")
        target = self.root / self.ARC_A
        target.unlink()
        target.symlink_to(linked)
        config, manifest = workflow.load_state(self.root)
        unit = next(item for item in manifest["units"] if item["id"] == "arc-a")

        report = workflow.qa_unit(self.root, config, manifest, unit)
        self.assertFalse(report["pass"])
        self.assertTrue(any("file mode changed" in issue for issue in report["errors"]), report["errors"])

    def test_context_segments_and_progress_default_to_the_active_unit(self):
        self.start_arc_a()

        context_code, context_output, context_error = self.invoke("context")
        self.assertEqual(context_code, 0, context_error)
        self.assertEqual(json.loads(context_output)["unit"]["id"], "arc-a")

        segments_code, segments_output, segments_error = self.invoke("segments")
        self.assertEqual(segments_code, 0, segments_error)
        segments = json.loads(segments_output)
        self.assertEqual(segments[0]["headings"], ["A1. The Gate"])

        progress_code, progress_output, progress_error = self.invoke("progress")
        self.assertEqual(progress_code, 0, progress_error)
        progress = json.loads(progress_output)
        self.assertEqual(progress["unit_id"], "arc-a")
        self.assertTrue(progress["segments"])
        self.assertTrue(all(item["status"] == "pending" for item in progress["segments"]))

        notes = self.root / workflow.STATE_REL / "segment-notes.txt"
        notes.write_text("Translated the opening and recorded the Death House naming decision.", encoding="utf-8")
        done_code, _, done_error = self.invoke(
            "segment-done", "arc-a", "1", "--agent", "translator-a", "--notes-file", str(notes)
        )
        self.assertEqual(done_code, 0, done_error)
        _, refreshed_output, _ = self.invoke("progress")
        refreshed = json.loads(refreshed_output)
        self.assertEqual(refreshed["segments"][0]["status"], "completed")
        self.assertEqual(refreshed["segments"][0]["completed_by"], "translator-a")

    def test_finish_rejects_an_approved_unit_with_pending_segments(self):
        self.start_arc_a()
        manifest_path = self.root / workflow.STATE_REL / workflow.MANIFEST_NAME
        manifest = self.load_manifest()
        arc_a = next(item for item in manifest["units"] if item["id"] == "arc-a")
        arc_a["status"] = "approved"
        workflow.atomic_write_json(manifest_path, manifest)

        return_code, _, error = self.invoke("finish", "arc-a")
        self.assertEqual(return_code, 2)
        self.assertIn("every planned segment", error)

    def test_status_detects_static_support_drift_and_reseal_restores_health(self):
        status_code, status_output, status_error = self.invoke("status", "--json")
        self.assertEqual(status_code, 0, status_error)
        self.assertTrue(json.loads(status_output)["workflow_seal_ok"])

        skill_path = self.root / workflow.SKILL_REL / "SKILL.md"
        skill_path.write_text(skill_path.read_text(encoding="utf-8") + "\n<!-- reviewed test change -->\n", encoding="utf-8")
        drift_code, drift_output, _ = self.invoke("status", "--json")
        self.assertEqual(drift_code, 2)
        self.assertFalse(json.loads(drift_output)["workflow_seal_ok"])

        seal_code, _, seal_error = self.invoke(
            "seal-workflow", "--reason", "Reviewed static workflow fixture update"
        )
        self.assertEqual(seal_code, 0, seal_error)
        healthy_code, healthy_output, healthy_error = self.invoke("status", "--json")
        self.assertEqual(healthy_code, 0, healthy_error)
        self.assertTrue(json.loads(healthy_output)["workflow_seal_ok"])

    def test_sealed_visual_inventory_is_an_allowed_support_path(self):
        state = self.root / workflow.STATE_REL
        workflow.atomic_write_json(state / "visual-assets.json", {"schema_version": 1, "assets": []})
        config_path = state / workflow.CONFIG_NAME
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["sealed_support_hashes"] = workflow.compute_static_support_hashes(self.root)
        workflow.atomic_write_json(config_path, config)
        workflow.write_config_seal(self.root, config_path)

        status_code, status_output, status_error = self.invoke("status", "--json")
        self.assertEqual(status_code, 0, status_error)
        payload = json.loads(status_output)
        self.assertTrue(payload["healthy"], payload)
        self.assertEqual(payload["unexpected_dirty_paths"], [])

    def test_optional_legacy_reference_pack_is_sealed_provenance_not_dirty_scratch(self):
        legacy = self.root / workflow.LEGACY_REFERENCE_REL
        legacy.mkdir(parents=True)
        source = legacy / "common-kalkas.md"
        source.write_text("# Untrusted provenance\n", encoding="utf-8")
        state = self.root / workflow.STATE_REL
        config_path = state / workflow.CONFIG_NAME
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["sealed_support_hashes"] = workflow.compute_static_support_hashes(self.root)
        workflow.atomic_write_json(config_path, config)
        workflow.write_config_seal(self.root, config_path)

        healthy_code, healthy_output, healthy_error = self.invoke("status", "--json")
        self.assertEqual(healthy_code, 0, healthy_error)
        self.assertTrue(json.loads(healthy_output)["healthy"])

        source.write_text("# Unreviewed drift\n", encoding="utf-8")
        drift_code, drift_output, _ = self.invoke("status", "--json")
        self.assertEqual(drift_code, 2)
        self.assertFalse(json.loads(drift_output)["workflow_seal_ok"])

    def test_seal_workflow_cannot_reapprove_unsealed_config_edits(self):
        state = self.root / workflow.STATE_REL
        config_path = state / workflow.CONFIG_NAME
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["minimum_review_score"] = 0
        config["required_review_roles"] = []
        workflow.atomic_write_json(config_path, config)
        self.assertFalse(workflow.config_seal_ok(self.root))

        seal_code, _, seal_error = self.invoke(
            "seal-workflow", "--reason", "reviewed prose support"
        )
        self.assertEqual(seal_code, 2)
        self.assertIn("support drift only, not config edits", seal_error)
        self.assertFalse(workflow.config_seal_ok(self.root))

    def test_config_contract_rejects_weak_gates_even_with_matching_hash_seal(self):
        state = self.root / workflow.STATE_REL
        config_path = state / workflow.CONFIG_NAME
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["minimum_review_score"] = 0
        config["required_review_roles"] = []
        workflow.atomic_write_json(config_path, config)
        workflow.write_config_seal(self.root, config_path)

        status_code, status_output, status_error = self.invoke("status", "--json")
        self.assertEqual(status_code, 2, status_error)
        errors = json.loads(status_output)["source_metadata_errors"]
        self.assertTrue(any("minimum review score" in item for item in errors), errors)
        self.assertTrue(any("fidelity and Russian-style" in item for item in errors), errors)
        seal_code, _, seal_error = self.invoke(
            "seal-workflow", "--reason", "attempted weak-gate reseal"
        )
        self.assertEqual(seal_code, 2)
        self.assertIn("weakened/invalid config", seal_error)

    def test_committed_or_symlinked_workflow_support_cannot_bypass_the_seal(self):
        skill_file = self.root / workflow.SKILL_REL / "SKILL.md"
        skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\ncommitted drift\n", encoding="utf-8")
        self._git("add", str(skill_file.relative_to(self.root)))
        self._git("commit", "-m", "unreviewed committed workflow drift")
        status_code, status_output, _ = self.invoke("status", "--json")
        self.assertEqual(status_code, 2)
        self.assertFalse(json.loads(status_output)["workflow_seal_ok"])
        start_code, _, start_error = self.invoke("start", "arc-a", "--translator", "translator-a")
        self.assertEqual(start_code, 2)
        self.assertIn("workflow-support", start_error)

        skill_root = self.root / workflow.SKILL_REL
        external = self.root / "external-skill-copy"
        shutil.copytree(skill_root, external)
        shutil.rmtree(skill_root)
        skill_root.symlink_to(external, target_is_directory=True)
        symlink_code, symlink_output, _ = self.invoke("status", "--json")
        self.assertEqual(symlink_code, 2)
        self.assertFalse(json.loads(symlink_output)["workflow_seal_ok"])

    def test_status_rejects_a_manifest_that_omits_pinned_content(self):
        manifest_path = self.root / workflow.STATE_REL / workflow.MANIFEST_NAME
        manifest = self.load_manifest()
        manifest["units"] = [item for item in manifest["units"] if item["id"] != "arc-b"]
        workflow.atomic_write_json(manifest_path, manifest)

        code, output, error = self.invoke("status")
        self.assertEqual(code, 2, error)
        self.assertIn("omits pinned content", output)

    def test_status_and_start_reject_symlinked_mutable_core_state(self):
        manifest_path = self.root / workflow.STATE_REL / workflow.MANIFEST_NAME
        external = self.root / "external-manifest.json"
        external.write_bytes(manifest_path.read_bytes())
        manifest_path.unlink()
        manifest_path.symlink_to(external)

        status_code, status_output, status_error = self.invoke("status", "--json")
        self.assertEqual(status_code, 2, status_error)
        payload = json.loads(status_output)
        self.assertFalse(payload["healthy"])
        self.assertTrue(
            any("core state is missing/non-regular/wrong-mode" in issue for issue in payload["source_metadata_errors"]),
            payload["source_metadata_errors"],
        )
        start_code, _, start_error = self.invoke("start", "arc-a", "--translator", "translator-a")
        self.assertEqual(start_code, 2)
        self.assertIn("translation state integrity failure", start_error)

    def test_malformed_authority_tsv_cannot_disable_glossary_enforcement(self):
        glossary = self.root / workflow.STATE_REL / "glossary.tsv"
        glossary.write_text(
            "source,approved_ru,status,enforce\nStrahd,Страд,approved,yes\n",
            encoding="utf-8",
        )

        status_code, status_output, status_error = self.invoke("status", "--json")
        self.assertEqual(status_code, 2, status_error)
        payload = json.loads(status_output)
        self.assertTrue(
            any("TSV header is noncanonical" in issue for issue in payload["source_metadata_errors"]),
            payload["source_metadata_errors"],
        )
        start_code, _, start_error = self.invoke("start", "arc-a", "--translator", "translator-a")
        self.assertEqual(start_code, 2)
        self.assertIn("authority TSV header is noncanonical", start_error)

    def test_duplicate_style_watch_literals_block_status_and_mutation(self):
        state = self.root / workflow.STATE_REL
        rows = []
        for rule_id in ("RUQ-900", "RUQ-901"):
            row = {
                "id": rule_id,
                "status": "candidate",
                "literals": "в рамках",
                "category": "bureaucratic-frame",
                "guidance": "Review the frame.",
                "applicability": "Visible prose.",
                "exceptions": "Institutional speech.",
                "evidence": "test evidence",
                "origin_unit": "test-unit",
                "notes": "Duplicate test.",
            }
            rows.append("\t".join(row.get(name, "") for name in workflow.STYLE_WATCH_HEADER))
        (state / workflow.STYLE_WATCH_NAME).write_text(
            "\t".join(workflow.STYLE_WATCH_HEADER) + "\n" + "\n".join(rows) + "\n",
            encoding="utf-8",
        )

        status_code, status_output, status_error = self.invoke("status", "--json")
        self.assertEqual(status_code, 2, status_error)
        payload = json.loads(status_output)
        self.assertTrue(
            any("duplicate style-watch literal" in issue for issue in payload["source_metadata_errors"]),
            payload["source_metadata_errors"],
        )
        start_code, _, start_error = self.invoke("start", "arc-a", "--translator", "translator-a")
        self.assertEqual(start_code, 2)
        self.assertIn("duplicate style-watch literal", start_error)

    def test_manifest_order_and_generated_hash_provenance_are_canonical(self):
        manifest_path = self.root / workflow.STATE_REL / workflow.MANIFEST_NAME
        manifest = self.load_manifest()
        manifest["units"].reverse()
        workflow.atomic_write_json(manifest_path, manifest)
        status_code, status_output, _ = self.invoke("status")
        self.assertEqual(status_code, 2)
        self.assertIn("canonical arc/supplement order", status_output)
        next_code, _, next_error = self.invoke("next")
        self.assertEqual(next_code, 2)
        self.assertIn("canonical arc/supplement order", next_error)

        manifest = self.load_manifest()
        manifest["units"].reverse()
        arc_a = next(item for item in manifest["units"] if item["id"] == "arc-a")
        arc_a["expected_head_sha256"] = "f" * 64
        workflow.atomic_write_json(manifest_path, manifest)
        provenance_code, provenance_output, _ = self.invoke("status")
        self.assertEqual(provenance_code, 2)
        self.assertIn("lacks generated-link provenance", provenance_output)

    def test_status_rejects_unknown_manifest_status_and_unrelated_dirty_paths(self):
        manifest_path = self.root / workflow.STATE_REL / workflow.MANIFEST_NAME
        manifest = self.load_manifest()
        next(item for item in manifest["units"] if item["id"] == "arc-a")["status"] = "done-ish"
        workflow.atomic_write_json(manifest_path, manifest)
        (self.root / "unrelated.tmp").write_text("unrelated", encoding="utf-8")
        (self.root / self.ARC_B).write_text("manual dirty prose\n", encoding="utf-8")

        code, output, error = self.invoke("status")
        self.assertEqual(code, 2, error)
        self.assertIn("invalid unit status", output)
        self.assertIn("unrelated.tmp", output)
        self.assertIn("arc-b", output)

    def test_empty_progress_list_cannot_bypass_the_pinned_segment_plan(self):
        self.start_arc_a()
        progress_path = self.root / workflow.STATE_REL / workflow.WORK_DIR / "arc-a" / "progress.json"
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        progress["segments"] = []
        workflow.atomic_write_json(progress_path, progress)

        code, _, error = self.invoke("progress", "arc-a")
        self.assertEqual(code, 2)
        self.assertIn("exactly cover", error)

    def test_sync_links_does_not_rewrite_wikilinks_in_code_or_html_comments(self):
        self.start_arc_a()
        self.write_target_a()

        return_code, _, error = self.invoke("sync-links", "arc-a")
        self.assertEqual(return_code, 0, error)
        linked_text = (self.root / self.ARC_B).read_text(encoding="utf-8")
        self.assertIn(
            "[[Arc A - Escape From Death House#A1. Врата|the gate]]",
            linked_text,
        )
        self.assertIn(f"`{self.SOURCE_LINK}`", linked_text)
        self.assertIn(f"<!-- {self.SOURCE_LINK} -->", linked_text)

    def test_finish_scope_accepts_generated_inbound_updates_with_crlf(self):
        inbound = self.root / self.ARC_B
        (self.root / ".gitattributes").write_text(f'"{self.ARC_B}" -text\n', encoding="utf-8")
        inbound.write_bytes(inbound.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8"))
        self._git("add", ".gitattributes", self.ARC_B)
        self._git("commit", "-m", "pin CRLF inbound source")
        init_code, _, init_error = self.invoke("init", "--source-ref", "HEAD", "--force")
        self.assertEqual(init_code, 0, init_error)
        self.start_arc_a()
        self.write_target_a()
        self.sync_arc_a()
        self.assertIn(b"\r\n", inbound.read_bytes())
        config, manifest = workflow.load_state(self.root)
        unit = next(item for item in manifest["units"] if item["id"] == "arc-a")

        workflow.ensure_finish_scope(self.root, config, manifest, unit)

    def test_sync_links_can_update_a_previously_synchronized_heading_revision(self):
        self.start_arc_a()
        self.write_target_a()
        self.sync_arc_a()
        target_path = self.root / self.ARC_A
        target_path.write_text(self.TARGET_A.replace("A1. Врата", "A1. Ворота"), encoding="utf-8")

        self.sync_arc_a()
        linked_text = (self.root / self.ARC_B).read_text(encoding="utf-8")
        self.assertIn("#A1. Ворота|the gate", linked_text)
        self.assertNotIn("#A1. Врата|the gate", linked_text)

    def test_repeated_sync_refreshes_consistency_review_target_hash(self):
        self.mark_arc_b_completed()
        self.start_arc_a()
        self.write_target_a()
        self.sync_arc_a()
        first = self.unit("arc-b")["consistency_review"]["target_sha256"]

        target_path = self.root / self.ARC_A
        target_path.write_text(self.TARGET_A.replace("A1. Врата", "A1. Ворота"), encoding="utf-8")
        self.sync_arc_a()
        record = self.unit("arc-b")["consistency_review"]
        current = workflow.sha256_bytes((self.root / self.ARC_B).read_bytes())
        self.assertNotEqual(first, current)
        self.assertEqual(record["target_sha256"], current)
        self.assertTrue(record["history"])

    def test_sync_links_invalidates_a_previously_completed_inbound_unit(self):
        self.mark_arc_b_completed()

        self.start_arc_a()
        self.write_target_a()
        return_code, _, error = self.invoke("sync-links", "arc-a")
        self.assertEqual(return_code, 0, error)

        refreshed = self.unit("arc-b")
        self.assertEqual(refreshed["status"], "consistency_review")
        self.assertNotEqual(
            refreshed.get("target_sha256"),
            workflow.sha256_bytes((self.root / self.ARC_B).read_bytes()),
            "the old completion hash must not remain valid after a generated inbound-link edit",
        )

    def test_link_reviewer_must_be_independent_from_triggering_translator(self):
        self.mark_arc_b_completed()
        self.start_arc_a()
        self.write_target_a()
        self.sync_arc_a()
        self.record_test_completion("arc-a", "translator-a")
        notes = self.root / "link-notes.txt"
        notes.write_text("Checked generated navigation.", encoding="utf-8")

        code, output, error = self.invoke(
            "revalidate-links", "arc-b", "--reviewer", "translator-a", "--notes-file", str(notes)
        )
        self.assertEqual(code, 2)
        self.assertIn("triggering translators", error)

    def test_link_style_delta_requires_preflight_and_independent_dispositions(self):
        state = self.root / workflow.STATE_REL
        row = {
            "id": "RUQ-900",
            "status": "approved",
            "literals": "в рамках",
            "category": "bureaucratic-frame",
            "guidance": "Review whether the frame is empty.",
            "applicability": "Visible prose and labels.",
            "exceptions": "Institutional speech may justify it.",
            "evidence": "test evidence",
            "origin_unit": "test-unit",
            "reviewer": "test-reviewer",
            "decision_date": "2026-07-12",
            "notes": "Navigation regression fixture.",
        }
        (state / workflow.STYLE_WATCH_NAME).write_text(
            "\t".join(workflow.STYLE_WATCH_HEADER)
            + "\n"
            + "\t".join(row.get(name, "") for name in workflow.STYLE_WATCH_HEADER)
            + "\n",
            encoding="utf-8",
        )
        inbound = self.root / self.ARC_B
        inbound.write_text(
            "# B1. Прибытие\n"
            "См. [[Arc A - Escape From Death House#A1. The Gate]].\n"
            f"`{self.SOURCE_LINK}`\n"
            f"<!-- {self.SOURCE_LINK} -->\n",
            encoding="utf-8",
        )
        self._git("add", self.ARC_B)
        self._git("commit", "-m", "completed implicit-link fixture")
        self.record_test_completion("arc-b", "translator-b")
        self._git("add", str(workflow.STATE_REL))
        self._git("commit", "-m", "completed implicit-link evidence fixture")

        self.start_arc_a()
        (self.root / self.ARC_A).write_text(
            "# A1. В рамках\nГерои входят в Дом Смерти.\n", encoding="utf-8"
        )
        inbound_before = inbound.read_bytes()
        sync_code, _, sync_error = self.invoke("sync-links", "arc-a")
        self.assertEqual(sync_code, 2)
        self.assertIn("would change Russian-reviewed style-watch evidence", sync_error)
        self.assertEqual(inbound.read_bytes(), inbound_before, "failed preflight must write nothing")
        sync_code, _, sync_error = self.invoke(
            "sync-links",
            "arc-a",
            "--allow-style-delta",
            "--style-delta-reason",
            "Reviewed implicit heading label; defer final acceptance to independent delta review.",
        )
        self.assertEqual(sync_code, 0, sync_error)
        previous_report = state / workflow.REPORTS_DIR / "arc-b.json"
        previous_bytes = previous_report.read_bytes()
        notes = state / workflow.WORK_DIR / "arc-a" / "link-style-notes.txt"
        notes.write_text("Checked the generated implicit heading label.", encoding="utf-8")

        code, output, error = self.invoke(
            "revalidate-links",
            "arc-b",
            "--reviewer",
            "independent-link-reviewer",
            "--notes-file",
            str(notes),
        )
        self.assertEqual(code, 2)
        self.assertIn("changed the reviewed Russian style-watch evidence", error, output)
        self.assertEqual(self.unit("arc-b")["status"], "consistency_review")
        self.assertEqual(previous_report.read_bytes(), previous_bytes)

        config, manifest = workflow.load_state(self.root)
        inbound_unit = next(item for item in manifest["units"] if item["id"] == "arc-b")
        current_report = workflow.qa_unit(self.root, config, manifest, inbound_unit)
        self.assertTrue(current_report["pass"], current_report)
        self.assertEqual(len(current_report["style_flags"]), 1, current_report)
        dispositions = state / workflow.WORK_DIR / "arc-a" / "link-style-dispositions.json"
        workflow.atomic_write_json(
            dispositions,
            {
                "schema_version": 1,
                "unit_id": "arc-b",
                "target_sha256": current_report["target_sha256"],
                "style_flags_sha256": current_report["style_flags_sha256"],
                "dispositions": [
                    {
                        "key": current_report["style_flags"][0]["key"],
                        "decision": "accepted-context",
                        "reason": "The reviewed scene heading is a deliberate title, not empty bureaucratic framing.",
                    }
                ],
            },
        )
        style_notes = state / workflow.WORK_DIR / "arc-a" / "link-style-delta-notes.txt"
        style_notes.write_text(
            "Read the implicit Russian heading label in context and checked the current exact flag.",
            encoding="utf-8",
        )
        code, _, error = self.invoke(
            "revalidate-links",
            "arc-b",
            "--reviewer",
            "independent-link-reviewer",
            "--notes-file",
            str(notes),
            "--style-reviewer",
            "independent-style-delta",
            "--style-notes-file",
            str(style_notes),
            "--style-dispositions-file",
            str(dispositions),
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(self.unit("arc-b")["status"], "completed")
        self.assertEqual(self.unit("arc-a")["status"], "in_progress")
        link_record = json.loads(
            (state / workflow.REVIEWS_DIR / "arc-b" / "link-consistency.json").read_text(encoding="utf-8")
        )
        self.assertTrue(link_record["style_transition"]["changed"])
        self.assertEqual(
            link_record["style_transition"]["review"]["reviewer"], "independent-style-delta"
        )

    def test_multiple_inbound_consistency_reviews_can_close_sequentially(self):
        guide = self.root / self.GUIDE
        guide.write_text(
            "# Using This Guide\n"
            "This guide uses the 2014 Rules.\n"
            "See [[Arc A - Escape From Death House#A1. The Gate]].\n",
            encoding="utf-8",
        )
        self._git("add", self.GUIDE)
        self._git("commit", "-m", "add second pinned inbound link")
        init_code, _, init_error = self.invoke("init", "--source-ref", "HEAD", "--force")
        self.assertEqual(init_code, 0, init_error)

        self.mark_arc_b_completed()
        guide.write_text(
            "# Использование руководства\n"
            "Это руководство использует правила 2014 года.\n"
            "См. [[Arc A - Escape From Death House#A1. The Gate]].\n",
            encoding="utf-8",
        )
        self._git("add", self.GUIDE)
        self._git("commit", "-m", "completed second inbound translation fixture")
        guide_unit_id = next(
            item["id"] for item in self.load_manifest()["units"] if item["path"] == self.GUIDE
        )
        self.record_test_completion(guide_unit_id, "translator-guide")
        self._git("add", str(workflow.STATE_REL))
        self._git("commit", "-m", "completed second inbound evidence fixture")

        self.start_arc_a()
        self.write_target_a()
        self.sync_arc_a()
        self.assertEqual(self.unit("arc-b")["status"], "consistency_review")
        self.assertEqual(self.unit(guide_unit_id)["status"], "consistency_review")

        qa_code, _, qa_error = self.invoke("qa", "arc-a", "--write-report")
        self.assertEqual(qa_code, 0, qa_error)
        review_code, _, review_error = self.record_review("fidelity", "premature-reviewer")
        self.assertEqual(review_code, 2)
        self.assertIn("resolve generated inbound consistency reviews", review_error)
        lesson = self.root / "premature-lesson.txt"
        lesson.write_text("Do not finalize while navigation evidence is open.", encoding="utf-8")
        learn_code, _, learn_error = self.invoke(
            "learn",
            "arc-a",
            "--curator",
            "premature-curator",
            "--lesson-file",
            str(lesson),
            "--terms-reviewed",
            "--style-watch-reviewed",
        )
        self.assertEqual(learn_code, 2)
        self.assertIn("resolve generated inbound consistency reviews", learn_error)
        finish_code, _, finish_error = self.invoke("finish", "arc-a")
        self.assertEqual(finish_code, 2)
        self.assertIn("resolve generated inbound consistency reviews", finish_error)

        notes_b = self.root / "link-notes-b.txt"
        notes_b.write_text("Checked Arc B destination and implicit/explicit labels.", encoding="utf-8")
        code, _, error = self.invoke(
            "revalidate-links",
            "arc-b",
            "--reviewer",
            "link-reviewer-b",
            "--notes-file",
            str(notes_b),
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(self.unit("arc-b")["status"], "completed")
        self.assertEqual(self.unit(guide_unit_id)["status"], "consistency_review")

        notes_guide = self.root / "link-notes-guide.txt"
        notes_guide.write_text("Checked the guide's generated heading destination and label.", encoding="utf-8")
        code, _, error = self.invoke(
            "revalidate-links",
            guide_unit_id,
            "--reviewer",
            "link-reviewer-guide",
            "--notes-file",
            str(notes_guide),
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(self.unit(guide_unit_id)["status"], "completed")
        self.assertEqual(self.unit("arc-a")["status"], "auto_qa_pass")

    def test_authority_change_makes_written_qa_stale_before_second_review(self):
        self.start_arc_a()
        self.write_target_a()
        self.sync_arc_a()
        qa_code, _, qa_error = self.invoke("qa", "arc-a", "--write-report")
        self.assertEqual(qa_code, 0, qa_error)
        first_code, _, first_error = self.record_review("fidelity", "reviewer-fidelity")
        self.assertEqual(first_code, 0, first_error)

        style_path = self.root / workflow.STATE_REL / "style-guide.md"
        style_path.write_text(style_path.read_text(encoding="utf-8") + "\nUse a colder register.\n", encoding="utf-8")
        second_code, _, second_error = self.record_review("russian-style", "reviewer-style")

        self.assertEqual(second_code, 2)
        self.assertRegex(second_error.casefold(), r"authority|stale|rerun")
        self.assertEqual(self.unit("arc-a")["status"], "independent_review")

    def test_style_watch_authority_change_makes_written_qa_stale(self):
        self.start_arc_a()
        self.write_target_a()
        self.sync_arc_a()
        qa_code, _, qa_error = self.invoke("qa", "arc-a", "--write-report")
        self.assertEqual(qa_code, 0, qa_error)

        style_path = self.root / workflow.STATE_REL / workflow.STYLE_WATCH_NAME
        row = {
            "id": "RUQ-900",
            "status": "candidate",
            "literals": "звучит хорошо",
            "category": "response-calque",
            "guidance": "Review the source sense.",
            "applicability": "Visible prose.",
            "exceptions": "Literal sound can be correct.",
            "evidence": "test evidence",
            "origin_unit": "arc-a",
            "notes": "Candidate only.",
        }
        with style_path.open("a", encoding="utf-8") as handle:
            handle.write("\t".join(row.get(name, "") for name in workflow.STYLE_WATCH_HEADER) + "\n")

        review_code, _, review_error = self.record_review("fidelity", "reviewer-fidelity")
        self.assertEqual(review_code, 2)
        self.assertRegex(review_error.casefold(), r"authority|stale|rerun")

    def test_style_watch_flags_require_exact_russian_review_dispositions(self):
        state = self.root / workflow.STATE_REL
        style_path = state / workflow.STYLE_WATCH_NAME
        row = {
            "id": "RUQ-900",
            "status": "approved",
            "literals": "чувствуйте себя свободно",
            "category": "invitation-calque",
            "guidance": "Use a natural invitation when the source permits.",
            "applicability": "Visible instructions and dialogue.",
            "exceptions": "Intentional marked speech may retain it.",
            "evidence": "test sentence",
            "origin_unit": "arc-a",
            "reviewer": "test-reviewer",
            "decision_date": "2026-07-12",
            "notes": "Warning only.",
        }
        style_path.write_text(
            "\t".join(workflow.STYLE_WATCH_HEADER) + "\n"
            + "\t".join(row.get(name, "") for name in workflow.STYLE_WATCH_HEADER) + "\n",
            encoding="utf-8",
        )
        self.start_arc_a()
        (self.root / self.ARC_A).write_text(
            "# A1. Врата\nЧувствуйте себя свободно.\n", encoding="utf-8"
        )
        self.sync_arc_a()
        qa_code, _, qa_error = self.invoke("qa", "arc-a", "--write-report")
        self.assertEqual(qa_code, 0, qa_error)
        report_path = state / workflow.REPORTS_DIR / "arc-a.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertTrue(report["pass"])
        self.assertEqual(len(report["style_flags"]), 1, report)
        self.assertTrue(any("style-watch RUQ-900" in item for item in report["warnings"]))

        fail_code, _, fail_error = self.record_review(
            "russian-style", "reviewer-style-fail", verdict="fail"
        )
        self.assertEqual(fail_code, 0, fail_error)
        self.assertEqual(self.unit("arc-a")["status"], "needs_revision")

        fidelity_code, _, fidelity_error = self.record_review("fidelity", "reviewer-fidelity")
        self.assertEqual(fidelity_code, 0, fidelity_error)
        missing_code, _, missing_error = self.record_review("russian-style", "reviewer-style")
        self.assertEqual(missing_code, 2)
        self.assertIn("disposition every current style-watch flag", missing_error)

        flag_key = report["style_flags"][0]["key"]
        dispositions_path = state / workflow.WORK_DIR / "arc-a" / "style-dispositions.json"
        identity = {
            "schema_version": 1,
            "unit_id": "arc-a",
            "target_sha256": report["target_sha256"],
            "style_flags_sha256": report["style_flags_sha256"],
        }
        workflow.atomic_write_json(
            dispositions_path,
            {
                **identity,
                "dispositions": [
                    {"key": flag_key, "decision": "accepted-context", "reason": "Deliberate stiff invitation."},
                    {"key": flag_key, "decision": "false-positive", "reason": "Duplicate must be rejected."},
                ],
            },
        )
        duplicate_code, _, duplicate_error = self.record_review(
            "russian-style", "reviewer-style", style_dispositions=dispositions_path
        )
        self.assertEqual(duplicate_code, 2)
        self.assertIn("duplicate key", duplicate_error)

        workflow.atomic_write_json(
            dispositions_path,
            {
                **identity,
                "dispositions": [
                    {
                        "key": flag_key,
                        "decision": "accepted-context",
                        "reason": "The intentionally bureaucratic speaker uses this marked phrase in context.",
                    }
                ],
            },
        )
        style_code, _, style_error = self.record_review(
            "russian-style", "reviewer-style", style_dispositions=dispositions_path
        )
        self.assertEqual(style_code, 0, style_error)
        stored_review = json.loads(
            (state / workflow.REVIEWS_DIR / "arc-a" / "russian-style.json").read_text(encoding="utf-8")
        )
        workflow.validate_style_review_record(stored_review, report)

        lesson = state / workflow.WORK_DIR / "arc-a" / "lesson.txt"
        lesson.write_text("Review repeated calques only from sentence-level evidence.", encoding="utf-8")
        missing_learn_code, _, missing_learn_error = self.invoke(
            "learn", "arc-a", "--curator", "curator", "--lesson-file", str(lesson), "--terms-reviewed"
        )
        self.assertEqual(missing_learn_code, 2)
        self.assertIn("style-watch candidates", missing_learn_error)
        watch_before = style_path.read_bytes()
        learn_code, _, learn_error = self.invoke(
            "learn", "arc-a", "--curator", "curator", "--lesson-file", str(lesson),
            "--terms-reviewed", "--style-watch-reviewed"
        )
        self.assertEqual(learn_code, 0, learn_error)
        self.assertEqual(style_path.read_bytes(), watch_before, "learn must never auto-promote style-watch rows")

    def test_required_review_role_and_unit_identity_cannot_be_forged(self):
        self.start_arc_a()
        self.write_target_a()
        self.sync_arc_a()
        qa_code, _, qa_error = self.invoke("qa", "arc-a", "--write-report")
        self.assertEqual(qa_code, 0, qa_error)
        self.assertEqual(self.record_review("fidelity", "reviewer-fidelity")[0], 0)
        self.assertEqual(self.record_review("russian-style", "reviewer-style")[0], 0)
        review_path = self.root / workflow.STATE_REL / workflow.REVIEWS_DIR / "arc-a" / "russian-style.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["role"] = "fidelity"
        review["unit_id"] = "wrong-unit"
        review["path"] = "wrong.md"
        workflow.atomic_write_json(review_path, review)
        config, manifest = workflow.load_state(self.root)
        unit = next(item for item in manifest["units"] if item["id"] == "arc-a")
        report = json.loads(
            (self.root / workflow.STATE_REL / workflow.REPORTS_DIR / "arc-a.json").read_text(encoding="utf-8")
        )

        with self.assertRaises(workflow.WorkflowError):
            workflow.passing_reviews(self.root, config, unit, report)

    def test_completed_evidence_rejects_review_quality_and_independence_tampering(self):
        self.mark_arc_b_completed()
        review_dir = self.root / workflow.STATE_REL / workflow.REVIEWS_DIR / "arc-b"
        fidelity = json.loads((review_dir / "fidelity.json").read_text(encoding="utf-8"))
        style = json.loads((review_dir / "russian-style.json").read_text(encoding="utf-8"))
        style["reviewer"] = fidelity["reviewer"]
        style["score"] = 0
        style["unresolved_issues"] = 2
        style["issue_counts"] = {"blocker": 1, "major": 1, "minor": 0}
        workflow.atomic_write_json(review_dir / "russian-style.json", style)
        config, manifest = workflow.load_state(self.root)
        errors = workflow.validate_source_metadata(self.root, config, manifest)
        self.assertTrue(any("quality gate" in issue for issue in errors), errors)
        self.assertTrue(any("not independent" in issue for issue in errors), errors)

    def test_completed_evidence_rejects_style_disposition_fingerprint_tampering(self):
        self.mark_arc_b_completed()
        review_path = (
            self.root / workflow.STATE_REL / workflow.REVIEWS_DIR / "arc-b" / "russian-style.json"
        )
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["style_flags_sha256"] = "f" * 64
        workflow.atomic_write_json(review_path, review)

        config, manifest = workflow.load_state(self.root)
        errors = workflow.validate_source_metadata(self.root, config, manifest)
        self.assertTrue(any("style-watch" in issue and "stale" in issue for issue in errors), errors)

    def test_completed_evidence_binds_work_artifacts_and_heading_map(self):
        self.mark_arc_b_completed()
        work_ledger = self.root / workflow.STATE_REL / workflow.WORK_DIR / "arc-b" / "ledger.md"
        work_ledger.write_text(work_ledger.read_text(encoding="utf-8") + "\nTampered after completion.\n", encoding="utf-8")
        heading_path = self.root / workflow.STATE_REL / workflow.HEADING_MAP_NAME
        heading_state = json.loads(heading_path.read_text(encoding="utf-8"))
        heading_state["files"].pop(self.ARC_B)
        workflow.atomic_write_json(heading_path, heading_state)

        config, manifest = workflow.load_state(self.root)
        errors = workflow.validate_source_metadata(self.root, config, manifest)
        self.assertTrue(any("work evidence hash drifted" in issue for issue in errors), errors)
        self.assertTrue(any("heading-map entry is missing or stale" in issue for issue in errors), errors)

    def test_reopen_archives_completed_evidence_and_starts_full_semantic_revision(self):
        self.mark_arc_b_completed()
        style = self.root / workflow.STATE_REL / "style-guide.md"
        style.write_text(style.read_text(encoding="utf-8") + "\nReviewed terminology revision.\n", encoding="utf-8")
        code, _, error = self.invoke(
            "reopen",
            "arc-b",
            "--translator",
            "revision-translator",
            "--reason",
            "reviewed authority change affects procedural prose",
        )
        self.assertEqual(code, 0, error)
        unit = self.unit("arc-b")
        self.assertEqual(unit["status"], "in_progress")
        self.assertEqual(unit["revision_number"], 1)
        self.assertTrue(unit["revision_history"])
        self.assertTrue((self.root / workflow.STATE_REL / workflow.REPORTS_DIR / "history").exists())
        archived_ledgers = list(
            (self.root / workflow.STATE_REL / workflow.WORK_DIR / "arc-b" / "history").glob("*/ledger.md")
        )
        self.assertTrue(archived_ledgers)
        active_ledger = self.root / workflow.STATE_REL / workflow.WORK_DIR / "arc-b" / "ledger.md"
        self.assertIn(archived_ledgers[0].relative_to(self.root).as_posix(), active_ledger.read_text(encoding="utf-8"))
        progress_code, progress_output, progress_error = self.invoke("progress", "arc-b")
        self.assertEqual(progress_code, 0, progress_error)
        self.assertTrue(json.loads(progress_output)["segments"])

    def test_link_revalidation_survives_later_lessons_memory_change(self):
        self.mark_arc_b_completed()
        self.start_arc_a()
        self.write_target_a()
        self.sync_arc_a()
        self.record_test_completion("arc-a", "translator-a")
        lessons = self.root / workflow.STATE_REL / "lessons.md"
        existing_lessons = lessons.read_text(encoding="utf-8") if lessons.exists() else "# Lessons\n"
        lessons.write_text(existing_lessons + "\nLater reviewed lesson.\n", encoding="utf-8")
        notes = self.root / workflow.STATE_REL / workflow.WORK_DIR / "arc-a" / "link-review-notes.txt"
        notes.write_text("Checked the updated destination and visible alias.", encoding="utf-8")
        code, _, error = self.invoke(
            "revalidate-links", "arc-b", "--reviewer", "independent-link-reviewer", "--notes-file", str(notes)
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(self.unit("arc-b")["status"], "completed")
        config, manifest = workflow.load_state(self.root)
        self.assertFalse(workflow.validate_source_metadata(self.root, config, manifest))

        link_path = self.root / workflow.STATE_REL / workflow.REVIEWS_DIR / "arc-b" / "link-consistency.json"
        link_record = json.loads(link_path.read_text(encoding="utf-8"))
        link_record["trigger"].pop("trigger_translator", None)
        workflow.atomic_write_json(link_path, link_record)
        errors = workflow.validate_source_metadata(self.root, config, manifest)
        self.assertTrue(any("link-consistency evidence is stale or invalid" in item for item in errors), errors)

    def test_full_completion_evidence_and_generated_update_commit_handoff(self):
        self.start_arc_a()
        self.write_target_a()
        self.sync_arc_a()
        work = self.root / workflow.STATE_REL / workflow.WORK_DIR / "arc-a"
        segment_notes = work / "segment-notes.txt"
        segment_notes.write_text("Translated the full fixture segment and checked continuity.", encoding="utf-8")
        done_code, _, done_error = self.invoke(
            "segment-done", "arc-a", "1", "--agent", "translator-a", "--notes-file", str(segment_notes)
        )
        self.assertEqual(done_code, 0, done_error)
        ledger = work / "ledger.md"
        ledger.write_text(ledger.read_text(encoding="utf-8") + "\nReviewed: Death House naming is consistent.\n", encoding="utf-8")
        qa_code, _, qa_error = self.invoke("qa", "arc-a", "--write-report")
        self.assertEqual(qa_code, 0, qa_error)
        self.assertEqual(self.record_review("fidelity", "reviewer-fidelity")[0], 0)
        self.assertEqual(self.record_review("russian-style", "reviewer-style")[0], 0)
        lesson = work / "lesson.txt"
        lesson.write_text("Preserve the concise procedural register in entry scenes.", encoding="utf-8")
        learn_code, _, learn_error = self.invoke(
            "learn", "arc-a", "--curator", "curator-a", "--lesson-file", str(lesson),
            "--terms-reviewed", "--style-watch-reviewed"
        )
        self.assertEqual(learn_code, 0, learn_error)
        finish_code, _, finish_error = self.invoke("finish", "arc-a")
        self.assertEqual(finish_code, 0, finish_error)
        config, manifest = workflow.load_state(self.root)
        self.assertFalse(workflow.validate_source_metadata(self.root, config, manifest))

        early_code, _, early_error = self.invoke("start", "arc-b", "--translator", "translator-b")
        self.assertEqual(early_code, 2)
        self.assertIn("commit the generated", early_error)
        self.assertEqual(self.unit("arc-b")["status"], "pending")

        self._git("add", self.ARC_A, self.ARC_B, str(workflow.STATE_REL))
        self._git("commit", "-m", "complete arc A fixture")
        start_code, _, start_error = self.invoke("start", "arc-b", "--translator", "translator-b")
        self.assertEqual(start_code, 0, start_error)


if __name__ == "__main__":
    unittest.main()
