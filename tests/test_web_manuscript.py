"""Conversion-contract tests; no network or LaTeX installation is required."""

import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_web_manuscript", ROOT / "scripts/build_web_manuscript.py")
web = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(web)


class SourceParsingTests(unittest.TestCase):
    def test_comments_do_not_publish_inactive_content(self):
        value = web.strip_comments("before% hidden\nafter\\% literal\n%\\input{inactive}\n")
        self.assertEqual(value, "beforeafter\\% literal\n")

    def test_blank_line_after_comment_remains_paragraph_break(self):
        value = web.strip_comments("first paragraph% hidden\n\nsecond paragraph\n")
        self.assertIn("first paragraph\n\nsecond paragraph", value)

    def test_verbatim_percent_is_literal(self):
        value = "\\begin{verbatim}\n20% literal\n\\end{verbatim}\n"
        self.assertEqual(web.strip_comments(value), value)

    def test_nested_groups(self):
        value, end = web.group(r"{A {nested} \{literal\}} tail", 0)
        self.assertEqual(value, r"A {nested} \{literal\}")
        self.assertEqual(r"{A {nested} \{literal\}} tail"[end:], " tail")

    def test_flatten_only_active_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "main.tex").write_text("%\\input{missing}\n\\input{child}", encoding="utf-8")
            (root / "child.tex").write_text("Active text", encoding="utf-8")
            seen = []
            result = web.flatten(root / "main.tex", root, seen)
            self.assertIn("Active text", result)
            self.assertEqual(len(seen), 2)

    def test_input_cycles_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "main.tex").write_text(r"\input{main}", encoding="utf-8")
            with self.assertRaises(web.ConversionError):
                web.flatten(root / "main.tex", root, [])


class NumberingTests(unittest.TestCase):
    def test_rows_do_not_split_matrix(self):
        rows = web.split_math_rows(r"A&=\begin{pmatrix}1&2\\3&4\end{pmatrix}\\b&=c")
        self.assertEqual(len(rows), 2)

    def test_numbering_and_subnumbering_match_aux(self):
        labels = {key: {"number": number} for key, number in {"one": "1", "group": "2", "a": "2a", "b": "2b"}.items()}
        source = (r"\begin{equation}x=y\label{one}\end{equation}"
                  r"\begin{subequations}\label{group}\begin{align}a&=b\label{a}\\c&=d\label{b}\end{align}\end{subequations}")
        numbering = web.EquationNumbering(labels)
        result = numbering.apply(source)
        self.assertIn(r"\tag{1}", result)
        self.assertIn(r"\tag{2a}", result)
        self.assertIn(r"\tag{2b}", result)
        self.assertEqual(numbering.numbered_rows, 3)
        self.assertEqual(numbering.checked_labels, set(labels))

    def test_stale_numbering_fails(self):
        numbering = web.EquationNumbering({"x": {"number": "8"}})
        with self.assertRaises(web.ConversionError):
            numbering.apply(r"\begin{equation}x=y\label{x}\end{equation}")

    def test_nonumber_does_not_advance_counter(self):
        numbering = web.EquationNumbering({"x": {"number": "1"}})
        result = numbering.apply(r"\begin{align}a&=b\nonumber\\c&=d\label{x}\end{align}")
        self.assertEqual(result.count(r"\tag{"), 1)

    def test_theorem_title_and_body_survive(self):
        source = r"\begin{proposition}[A title]\label{p}Body text.\end{proposition}"
        result = web.prepare_theorems(source, {"p": {"number": "1"}})
        self.assertIn("Proposition 1 (A title)", result)
        self.assertIn("Body text.", result)
        self.assertIn(r"\label{p}", result)

    def test_corollaries_have_independent_checked_counters(self):
        source = (r"\begin{proposition}\label{p1}First.\end{proposition}"
                  r"\begin{corollary}[An implication]\label{c1}Implication.\end{corollary}"
                  r"\begin{proposition}\label{p2}Second.\end{proposition}"
                  r"\begin{corollary}\label{c2}Another.\end{corollary}")
        labels = {key: {"number": number} for key, number in
                  {"p1": "1", "c1": "1", "p2": "2", "c2": "2"}.items()}
        result = web.prepare_theorems(source, labels)
        for heading in ("Proposition 1.", "Proposition 2.",
                        "Corollary 1 (An implication).", "Corollary 2."):
            self.assertIn(heading, result)
        self.assertEqual(result.count(r"\begin{quote}"), 4)
        self.assertEqual(result.count(r"\end{quote}"), 4)
        self.assertNotIn(r"\begin{corollary}", result)
        labels["c2"]["number"] = "3"
        with self.assertRaisesRegex(web.ConversionError, "Theorem numbering mismatch"):
            web.prepare_theorems(source, labels)


class CitationAndValidationTests(unittest.TestCase):
    def test_citation_locator_and_multiple_keys(self):
        citations = {"a": {"author": "One", "year": "2000"}, "b": {"author": "Two", "year": "2001"}}
        value, used = web.prepare_citations(r"\citet[p.~7]{a}; \citep{a,b}", citations)
        self.assertIn("One (2000, p.~7)", value)
        self.assertIn("One, 2000", value)
        self.assertIn("Two, 2001", value)
        self.assertEqual(used, {"a", "b"})

    def test_unrecognized_raw_tex_fails(self):
        ast = {"blocks": [{"t": "RawBlock", "c": ["latex", r"\unknown{important content}"]}]}
        with self.assertRaises(web.ConversionError):
            web.transform_ast(ast, {})

    def test_reference_uses_compiled_item_number(self):
        ast = {"blocks": [{"t": "Para", "c": [{"t": "RawInline", "c": ["latex", r"\ref{case}"]}]}]}
        web.transform_ast(ast, {"case": {"number": "1(iv)"}})
        self.assertEqual(ast["blocks"][0]["c"][0]["c"][1][0]["c"], "1(iv)")

    def test_literal_path_becomes_code_without_inventing_a_link(self):
        value = "scripts/report_competitive_main_comparison.py"
        for kind in ("RawInline", "RawBlock"):
            with self.subTest(kind=kind):
                raw = {"t": kind, "c": ["latex", r"\path{" + value + "}"]}
                ast = {"blocks": [{"t": "Para", "c": [raw]}] if kind == "RawInline" else [raw]}
                web.transform_ast(ast, {})
                self.assertEqual(ast["blocks"][0]["c"],
                                 [{"t": "Code", "c": [["", [], []], value]}])
                self.assertNotIn('"Link"', json.dumps(ast))

    def test_supplement_reference_targets_main_label(self):
        label = {"paper-p": {"number": "2", "html_target": "p"}}
        for node in (
            {"t": "RawInline", "c": ["latex", r"\ref{paper-p}"]},
            {"t": "Link", "c": [["", [], [["reference", "paper-p"]]], [], ["#paper-p", ""]]},
        ):
            ast = {"blocks": [{"t": "Para", "c": [node]}]}
            web.transform_ast(ast, label)
            self.assertEqual(ast["blocks"][0]["c"][0]["c"][2][0], "#p")

    def test_digital_deep_link_stays_within_reader(self):
        node = {"t": "Link", "c": [["", [], []], [],
                ["https://oliverpardo1979.github.io/ai-growth-and-labor/#additional-results", ""]]}
        ast = {"blocks": [{"t": "Para", "c": [node]}]}
        web.transform_ast(ast, {})
        self.assertEqual(node["c"][2][0], "#additional-results")

    def test_frontmatter_separators_are_preserved(self):
        ast = {"blocks": [{"t": "Para", "c": [
            {"t": "RawInline", "c": ["latex", r"\quad"]},
            {"t": "RawInline", "c": ["latex", r"\textbar"]}]}]}
        web.transform_ast(ast, {})
        self.assertEqual(ast["blocks"][0]["c"], [{"t": "Space"}, {"t": "Str", "c": "|"}])

    def test_unnumbered_paragraph_keeps_anchor_not_parent_number(self):
        ast = {"blocks": [{"t": "Header", "c": [4, ["p", [], []],
                [{"t": "Str", "c": "Numerical construction"}]]}]}
        sections = web.transform_ast(ast, {"p": {"number": "B.5", "destination": "section*.15"}})
        self.assertEqual(sections[0]["number"], "")
        self.assertEqual(ast["blocks"][0]["c"][1][0], "p")

    def test_literal_path_does_not_admit_other_raw_tex(self):
        for raw in (r"\path{scripts/a.py}\unknown{content}",
                    r"\path{\unknown{content}}", r"\path|scripts/a.py|"):
            with self.subTest(raw=raw), self.assertRaises(web.ConversionError):
                web.transform_ast({"blocks": [{"t": "RawBlock", "c": ["latex", raw]}]}, {})

    def test_corollary_gets_theorem_class(self):
        ast = {"blocks": [{"t": "BlockQuote", "c": [
            {"t": "Para", "c": [{"t": "Strong", "c": [
                {"t": "Str", "c": "Corollary 1 (Growth)."}]}]},
            {"t": "Para", "c": [{"t": "Str", "c": "Body."}]}
        ]}]}
        web.transform_ast(ast, {})
        self.assertEqual(ast["blocks"][0]["t"], "Div")
        self.assertEqual(ast["blocks"][0]["c"][0][1], ["theorem", "corollary"])
        self.assertIn("Body.", json.dumps(ast))


class DiagramCropTests(unittest.TestCase):
    def test_last_diagram_excludes_earlier_figure_and_prose(self):
        import pymupdf as fitz
        with fitz.open() as document:
            page = document.new_page(width=500, height=600)
            page.draw_rect(fitz.Rect(40, 30, 300, 110))
            page.insert_text((40, 150), "Earlier figure caption and discussion")
            page.draw_rect(fitz.Rect(70, 240, 350, 300))
            page.insert_text((90, 270), "Current diagram")
            clip = web.diagram_clip(page, 330)
            self.assertGreater(clip.y0, 200)
            self.assertGreater(clip.y1, 300)

    def test_axes_with_zero_area_remain_in_crop(self):
        import pymupdf as fitz
        with fitz.open() as document:
            page = document.new_page(width=500, height=600)
            page.draw_line((70, 200), (70, 400))
            page.draw_line((70, 400), (350, 400))
            page.draw_rect(fitz.Rect(90, 220, 320, 300))
            clip = web.diagram_clip(page, 440)
            self.assertLess(clip.y0, 200)
            self.assertGreater(clip.y1, 400)


class GeneratedManuscriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "docs/generated/manuscript-meta.json"
        if not path.exists():
            raise unittest.SkipTest("Run the web-manuscript build before integration tests")
        cls.meta = json.loads(path.read_text(encoding="utf-8"))
        cls.content = (path.parent / "manuscript.html").read_text(encoding="utf-8")

    def test_active_input_graph_and_hash_match(self):
        seen = []
        source = web.flatten(ROOT / "main_rewrite.tex", ROOT, seen)
        self.assertEqual(self.meta["source_files"], [p.relative_to(ROOT).as_posix() for p in seen])
        self.assertEqual(self.meta["source_sha256"], web.hashlib.sha256(source.encode("utf-8")).hexdigest())
        self.assertNotIn("sections_rewrite/11_rsi_limitations.tex", self.meta["source_files"])

    def test_every_active_label_has_an_html_target(self):
        source = web.flatten(ROOT / "main_rewrite.tex", ROOT, [])
        source += web.flatten(ROOT / "online_appendix.tex", ROOT, [])
        labels = set(re.findall(r"\\label\{([^}]+)\}", source))
        targets = re.findall(r'\bid="([^"]+)"', self.content)
        self.assertTrue(labels <= set(targets))
        self.assertEqual(len(targets), len(set(targets)))

    def test_complete_structural_inventory(self):
        source = web.flatten(ROOT / "main_rewrite.tex", ROOT, [])
        source += web.flatten(ROOT / "online_appendix.tex", ROOT, [])
        for kind in ("proposition", "corollary", "lemma", "definition", "assumption", "remark"):
            expected = len(re.findall(r"\\begin\{" + kind + r"\}", source))
            self.assertEqual(self.content.count('class="theorem ' + kind + '"'), expected)
        self.assertEqual(self.meta["counts"]["figures"], len(re.findall(r"\\begin\{figure\*?\}", source)))
        self.assertEqual(self.content.count("<figure "), self.meta["counts"]["figures"])
        self.assertEqual(self.content.count("<table "), self.meta["counts"]["tables"])
        self.assertEqual(self.content.count('class="csl-entry"'), self.meta["counts"]["bibliography_entries"])
        self.assertEqual(self.content.count('class="math display"'), self.meta["counts"]["display_math"])
        self.assertGreater(self.meta["validation"]["visible_text_tokens_verified"], 15000)

    def test_headings_keep_numbers_separate_from_titles(self):
        headings = self.meta["sections"]
        self.assertEqual(headings[0], {"id": "sec:rewrite-introduction", "title": "Introduction", "level": 1, "number": "1"})
        self.assertTrue(any(h["number"] == "B.1" for h in headings))
        self.assertTrue(any(h["number"] == "B.6" for h in headings))

    def test_uncapped_unit_construction_is_integrated_into_its_proof(self):
        self.assertNotIn("sections_rewrite/appendix_uncapped_unit.tex", self.meta["source_files"])
        self.assertNotIn('id="app:rewrite-uncapped-unit"', self.content)
        proof_start = self.content.index('id="proof:rewrite-uncapped-unit-bgp"')
        next_proof = self.content.index('id="proof:rewrite-research-scale"')
        integrated = self.content[proof_start:next_proof]
        for label in ("static-shares", "production", "feedback", "output-growth",
                      "capital-inference", "investment", "research-share", "consumption",
                      "deviations", "local-spectrum", "local-projection", "distribution",
                      "comparative-statics"):
            with self.subTest(label=label):
                self.assertIn(f'id="eq:rewrite-uncapped-unit-{label}"', integrated)

    def test_competitive_section_exercises_and_appendix_are_present(self):
        headings = {item["id"]: item for item in self.meta["sections"]}
        for key, number in {
            "sec:rewrite-competition": "5",
            "sec:rewrite-quantitative": "7",
            "subsec:rewrite-competitive-transition": "7.4",
            "subsec:rewrite-monopoly-growth-reversal": "S2",
            "sec:rewrite-conclusion": "8",
            "app:rewrite-competitive-transition": "S1",
        }.items():
            with self.subTest(key=key):
                self.assertEqual(headings[key]["number"], number)
        figure_ids = {item["id"] for item in self.meta["figures"]}
        for key in ("fig:rewrite-competitive-sigma15-levels",
                    "fig:rewrite-monopoly-growth-reversal-growth",
                    "fig:rewrite-monopoly-growth-reversal-technology",
                    "fig:rewrite-competitive-high-levels",
                    "fig:rewrite-competitive-low-distribution"):
            self.assertIn(key, figure_ids)
        self.assertEqual(self.content.count('class="theorem corollary"'), 2)

    def test_supplement_is_integrated_with_separate_provenance(self):
        seen = []
        source = web.flatten(ROOT / "online_appendix.tex", ROOT, seen)
        provenance = self.meta["supplement"]
        self.assertEqual(provenance["source_files"], [p.relative_to(ROOT).as_posix() for p in seen])
        self.assertEqual(provenance["source_sha256"], web.hashlib.sha256(source.encode("utf-8")).hexdigest())
        self.assertIn('id="additional-results"', self.content)
        self.assertIn('href="paper/online-appendix.pdf"', self.content)
        self.assertNotIn('href="#paper-', self.content)
        self.assertEqual(len([f for f in self.meta["figures"] if str(f["number"]).startswith("S")]), 10)

    def test_replication_paths_are_literal_code(self):
        for name in ("simulate_competitive_to_monopoly.py", "report_competitive_to_monopoly.py",
                     "report_competitive_main_comparison.py"):
            self.assertIn(f"<code>scripts/{name}</code>", self.content)

    def test_textual_endpoints_and_replication_are_retained(self):
        for text in ("Advances in artificial intelligence", "Declaration of AI use",
                     "Equilibrium checks", "Replication files", "Local convergence from nearby initial stocks."):
            self.assertIn(text, self.content)
        self.assertIn("ref-romer1990", self.content)
        self.assertIn("Journal of Political Economy", self.content)


if __name__ == "__main__":
    unittest.main()
