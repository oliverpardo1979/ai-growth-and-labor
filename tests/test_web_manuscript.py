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
        labels = set(re.findall(r"\\label\{([^}]+)\}", source))
        targets = re.findall(r'\bid="([^"]+)"', self.content)
        self.assertTrue(labels <= set(targets))
        self.assertEqual(len(targets), len(set(targets)))

    def test_complete_structural_inventory(self):
        source = web.flatten(ROOT / "main_rewrite.tex", ROOT, [])
        for kind in ("proposition", "lemma", "definition", "remark"):
            expected = len(re.findall(r"\\begin\{" + kind + r"\}", source))
            self.assertEqual(self.content.count('class="theorem ' + kind + '"'), expected)
        self.assertEqual(self.content.count("<figure "), self.meta["counts"]["figures"])
        self.assertEqual(self.content.count("<table "), self.meta["counts"]["tables"])
        self.assertEqual(self.content.count('class="csl-entry"'), self.meta["counts"]["bibliography_entries"])
        self.assertEqual(self.content.count('class="math display"'), self.meta["counts"]["display_math"])
        self.assertGreater(self.meta["validation"]["visible_text_tokens_verified"], 15000)

    def test_headings_keep_numbers_separate_from_titles(self):
        headings = self.meta["sections"]
        self.assertEqual(headings[0], {"id": "sec:rewrite-introduction", "title": "Introduction", "level": 1, "number": "1"})
        self.assertTrue(any(h["number"] == "B.1" for h in headings))
        self.assertTrue(any(h["number"] == "C.3" for h in headings))

    def test_textual_endpoints_and_replication_are_retained(self):
        for text in ("Advances in artificial intelligence", "Declaration of AI use",
                     "Equilibrium checks", "Replication files", "The uncapped economy with unit elasticity"):
            self.assertIn(text, self.content)
        self.assertIn("ref-romer1990", self.content)
        self.assertIn("Journal of Political Economy", self.content)


if __name__ == "__main__":
    unittest.main()
