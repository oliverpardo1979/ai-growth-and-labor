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
    APPENDIX_NUMBERING = (r"\appendix\numberwithin{equation}{section}"
                          r"\renewcommand{\theequation}{\thesection\arabic{equation}}")

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

    def test_appendix_sections_reset_but_subsections_and_starred_sections_do_not(self):
        numbers = {"main": "1", "main-next": "2", "a1": "A1", "a2": "A2", "a3": "A3", "b1": "B1"}
        labels = {key: {"number": number} for key, number in numbers.items()}
        source = (r"\section{Main}\begin{equation}x=y\label{main}\end{equation}"
                  r"\section{More main text}\begin{equation}x=y\label{main-next}\end{equation}"
                  + self.APPENDIX_NUMBERING +
                  r"\section[Proofs]{Proofs {and details}}\begin{equation}x=y\label{a1}\end{equation}"
                  r"\subsection{Another proof}\begin{equation*}x=y\end{equation*}"
                  r"\begin{align}x&=y\notag\\a&=b\label{a2}\end{align}"
                  r"\section*{An unnumbered heading}\begin{equation}x=y\label{a3}\end{equation}"
                  r"\section{Numerical methods}\begin{equation}x=y\label{b1}\end{equation}")
        numbering = web.EquationNumbering(labels)
        result = web.clean_layout(numbering.apply(source))
        self.assertEqual(re.findall(r"\\tag\{([^}]+)\}", result), list(numbers.values()))
        self.assertEqual(numbering.numbered_rows, 6)
        self.assertEqual(numbering.checked_labels, set(labels))
        self.assertIn(r"\section[Proofs]{Proofs {and details}}", result)
        self.assertIn(r"\section*{An unnumbered heading}", result)
        for command in (r"\appendix", r"\numberwithin", r"\renewcommand"):
            self.assertNotIn(command, result)

    def test_appendix_subequations_share_prefixed_parent_counter(self):
        labels = {key: {"number": number} for key, number in
                  {"parent": "A14", "a": "A14a", "b": "A14b", "next": "A15", "b1": "B1"}.items()}
        source = (self.APPENDIX_NUMBERING + r"\section{Proofs}"
                  + r"\begin{equation}x=y\end{equation}" * 13 +
                  r"\subsection{Grouped result}\begin{subequations}\label{parent}"
                  r"\begin{align}a&=b\label{a}\\b&=c\nonumber\\c&=d\label{b}\end{align}"
                  r"\end{subequations}\begin{equation}x=y\label{next}\end{equation}"
                  r"\section{Methods}\begin{equation}x=y\label{b1}\end{equation}")
        numbering = web.EquationNumbering(labels)
        tags = re.findall(r"\\tag\{([^}]+)\}", numbering.apply(source))
        self.assertEqual(tags, [f"A{i}" for i in range(1, 14)] + ["A14a", "A14b", "A15", "B1"])
        self.assertEqual(numbering.numbered_rows, 17)
        self.assertEqual(numbering.checked_labels, set(labels))

    def test_appendix_without_numberwithin_keeps_global_equation_counter(self):
        source = (r"\begin{equation}x=y\end{equation}\appendix\section{Proofs}"
                  r"\begin{equation}x=y\label{x}\end{equation}")
        result = web.EquationNumbering({"x": {"number": "2"}}).apply(source)
        self.assertEqual(re.findall(r"\\tag\{([^}]+)\}", result), ["1", "2"])

    def test_numberwithin_default_separator_is_not_silently_removed(self):
        source = (r"\appendix\numberwithin{equation}{section}\section{Proofs}"
                  r"\begin{equation}x=y\label{x}\end{equation}")
        result = web.EquationNumbering({"x": {"number": "A.1"}}).apply(source)
        self.assertIn(r"\tag{A.1}", result)

    def test_stale_or_missing_appendix_labels_fail(self):
        source = (self.APPENDIX_NUMBERING + r"\section{Proofs}"
                  r"\begin{equation}x=y\label{x}\end{equation}")
        for labels in ({}, {"x": {"number": "8"}}, {"x": {"number": "A.1"}},
                       {"x": {"number": "A2"}}, {"x": {"number": "B1"}}):
            with self.subTest(labels=labels), self.assertRaisesRegex(web.ConversionError, "Equation numbering mismatch"):
                web.EquationNumbering(labels).apply(source)

    def test_stale_appendix_subequation_parent_and_children_fail(self):
        source = (self.APPENDIX_NUMBERING + r"\section{Proofs}"
                  r"\begin{subequations}\label{parent}"
                  r"\begin{equation}x=y\label{child}\end{equation}\end{subequations}")
        for numbers in ({"parent": "A2", "child": "A1a"}, {"parent": "A1", "child": "A2a"}):
            labels = {key: {"number": number} for key, number in numbers.items()}
            with self.subTest(numbers=numbers), self.assertRaisesRegex(web.ConversionError, "Equation numbering mismatch"):
                web.EquationNumbering(labels).apply(source)

    def test_unsupported_equation_numbering_controls_fail_closed(self):
        for source in (r"\numberwithin{equation}{section}",
                       r"\appendix\numberwithin{equation}{subsection}",
                       r"\appendix\renewcommand{\theequation}{\thesection\arabic{equation}}",
                       r"\appendix\numberwithin{equation}{section}\renewcommand{\theequation}{\roman{equation}}"):
            with self.subTest(source=source), self.assertRaises(web.ConversionError):
                web.EquationNumbering({}).apply(source)

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

    def test_supplementary_sections_equations_and_theorems_match_aux(self):
        preamble = (r"\renewcommand{\thesection}{S\arabic{section}}"
                    r"\numberwithin{equation}{section}"
                    r"\newtheorem{proposition}{Proposition}"
                    r"\renewcommand{\theproposition}{S\arabic{proposition}}")
        labels = {key: {"number": number} for key, number in
                  {"eq": "S3.1", "next": "S4.1", "p": "S1"}.items()}
        numbering, prefixes = web.supplement_numbering(preamble, labels)
        source = (r"\section{Simulations}\section{Reversal}\section{Bounded results}"
                  r"\begin{equation}x=y\label{eq}\end{equation}"
                  r"\begin{proposition}[Low cap]\label{p}Statement.\end{proposition}"
                  r"\section{Uncapped results}\begin{equation}x=y\label{next}\end{equation}")
        result = web.prepare_theorems(numbering.apply(source), labels, prefixes)
        self.assertEqual(re.findall(r"\\tag\{([^}]+)\}", result), ["S3.1", "S4.1"])
        self.assertIn("Proposition S1 (Low cap)", result)
        self.assertEqual(numbering.checked_labels, {"eq", "next"})

    def test_supplementary_numbering_fails_closed_on_unsupported_formats(self):
        section = r"\renewcommand{\thesection}{S\arabic{section}}"
        for preamble in ("", section + r"\newtheorem{proposition}{Proposition}",
                         section + r"\renewcommand{\theequation}{S\arabic{equation}}"):
            with self.subTest(preamble=preamble), self.assertRaises(web.ConversionError):
                web.supplement_numbering(preamble, {})


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

    def test_supplement_resolves_unprefixed_and_legacy_main_references(self):
        labels = web.supplement_labels({"local": {"number": "S3.1"}}, {"main": {"number": "A2"}})
        ast = {"blocks": [{"t": "Para", "c": [
            {"t": "RawInline", "c": ["latex", r"\eqref{" + key + "}"]}
            for key in ("main", "paper-main", "local")]}]}
        web.transform_ast(ast, labels)
        links = ast["blocks"][0]["c"]
        self.assertEqual([node["c"][2][0] for node in links], ["#main", "#main", "#local"])
        self.assertEqual([node["c"][1][0]["c"] for node in links], ["(A2)", "(A2)", "(S3.1)"])

    def test_supplement_label_collisions_fail(self):
        for local in ({"same": {}}, {"paper-same": {}}):
            with self.subTest(local=local), self.assertRaises(web.ConversionError):
                web.supplement_labels(local, {"same": {}})

    def test_two_bibliographies_merge_and_fail_on_conflicts(self):
        merged = web.merge_bibliographies([("shared", "An entry."), ("main", "Main.")],
                                         [("shared", "An\nentry."), ("extra", "Extra.")])
        self.assertEqual([key for key, _ in merged], ["shared", "main", "extra"])
        with self.assertRaisesRegex(web.ConversionError, "Conflicting compiled bibliography"):
            web.merge_bibliographies([("key", "Old version")], [("key", "New version")])

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

    def test_supplementary_theorem_gets_theorem_class(self):
        ast = {"blocks": [{"t": "BlockQuote", "c": [
            {"t": "Para", "c": [{"t": "Strong", "c": [{"t": "Str", "c": "Proposition S1."}]}]},
            {"t": "Para", "c": [{"t": "Str", "c": "Statement."}]}]}]}
        web.transform_ast(ast, {})
        self.assertEqual(ast["blocks"][0]["c"][0][1], ["theorem", "proposition"])


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
        numerical_subsections = [h["number"] for h in headings
                                 if h["level"] == 2 and h["number"].startswith("B.")]
        self.assertEqual(numerical_subsections, ["B.1", "B.2"])

    def test_uncapped_unit_construction_is_integrated_into_its_proof(self):
        self.assertNotIn("sections_rewrite/appendix_uncapped_unit.tex", self.meta["source_files"])
        self.assertNotIn('id="app:rewrite-uncapped-unit"', self.content)
        proof_start = self.content.index('id="proof:rewrite-uncapped-unit-bgp"')
        next_proof = self.content.index('id="proof:rewrite-research-scale"')
        integrated = self.content[proof_start:next_proof]
        for label in ("static-shares", "production", "output-growth",
                      "capital-inference", "investment", "research-share", "consumption",
                      "deviations", "local-spectrum", "local-projection", "local-similarity",
                      "local-polynomial", "developer-verification"):
            with self.subTest(label=label):
                self.assertIn(f'id="eq:rewrite-uncapped-unit-{label}"', integrated)
        self.assertIn(r'<span class="math display">\[\Delta\equiv(1-\alpha)(1-\eta-\omega_X)&gt;0.\]</span>',
                      integrated)
        for label in ("feedback", "distribution", "comparative-statics", "output-row",
                      "research-row", "efficiency-row", "jacobian-k", "jacobian-b",
                      "jacobian-c", "jacobian-q"):
            with self.subTest(inactive_label=label):
                self.assertNotIn(f'id="eq:rewrite-uncapped-unit-{label}"', self.content)

    def test_proofs_are_grouped_by_economic_problem(self):
        headings = {h["id"]: h for h in self.meta["sections"]}
        keys = ("developer", "bounded", "competitive")
        positions = []
        for number, key in enumerate(keys, 1):
            label = f"app:rewrite-{key}-proofs"
            self.assertEqual(headings[label]["number"], f"A.{number}")
            positions.append(self.content.index(f'id="{label}"'))
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(headings["app:rewrite-uncapped-proofs"]["number"], "S4")
        supplementary = self.content.index('id="additional-results"')
        low_cap = self.content.index('id="prop:rewrite-low-cap-complements"')
        self.assertLess(supplementary, low_cap)
        self.assertLess(supplementary, self.content.index('id="rem:rewrite-efficiency-nonattainment"'))
        self.assertEqual(self.content.count('id="eq:rewrite-cap-gap"'), 1)
        self.assertLess(self.content.index('id="eq:rewrite-cap-gap"'), positions[1])

    def test_competitive_section_exercises_and_appendix_are_present(self):
        headings = {item["id"]: item for item in self.meta["sections"]}
        for key, number in {
            "sec:rewrite-competition": "5",
            "sec:rewrite-quantitative": "6",
            "subsec:rewrite-competitive-transition": "6.4",
            "subsec:rewrite-monopoly-growth-reversal": "S2",
            "sec:rewrite-conclusion": "7",
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

    def test_uncapped_results_are_in_main_appendix_c(self):
        headings = {item["id"]: item for item in self.meta["sections"]}
        for key, number in {
            "sec:rewrite-uncapped": "C",
            "subsec:rewrite-uncapped-complements": "C.1",
            "subsec:rewrite-uncapped-unit-bgp": "C.2",
            "subsec:rewrite-uncapped": "C.3",
        }.items():
            with self.subTest(key=key):
                self.assertEqual(headings[key]["number"], number)
        appendix = self.content.index('id="sec:rewrite-uncapped"')
        self.assertGreater(appendix, self.content.index('id="app:rewrite-algorithm"'))
        self.assertLess(appendix, self.content.index('id="additional-results"'))
        for label in ("uncapped-complements-bounds", "uncapped-unit-bgp", "research-scale"):
            with self.subTest(result=label):
                self.assertGreater(self.content.index(f'id="prop:rewrite-{label}"'), appendix)
                self.assertLess(self.content.index(f'id="prop:rewrite-{label}"'),
                                self.content.index('id="additional-results"'))
        self.assertEqual(headings["app:rewrite-uncapped-proofs"]["number"], "S4")

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

    def test_relocated_proofs_and_numerical_details_are_supplementary(self):
        main = web.flatten(ROOT / "main_rewrite.tex", ROOT, [])
        supplement = web.flatten(ROOT / "online_appendix.tex", ROOT, [])
        headings = {item["id"]: item for item in self.meta["sections"]}
        for key, number in {"app:rewrite-additional-bounded-results": "S3",
                            "app:rewrite-uncapped-proofs": "S4",
                            "app:rewrite-numerical-details": "S5"}.items():
            with self.subTest(key=key):
                label = r"\label{" + key + "}"
                self.assertNotIn(label, main)
                self.assertIn(label, supplement)
                self.assertEqual(headings[key]["number"], number)
        self.assertIn("Additional proofs and simulations", self.content)
        self.assertEqual(self.content.count('id="ref-kierzenkashampine2001"'), 1)

    def test_replication_details_are_linked_from_the_compact_appendix(self):
        self.assertIn('href="https://github.com/oliverpardo1979/ai-growth-and-labor/blob/main/REPLICATION.md"',
                      self.content)
        guide = (ROOT / "COMPETITIVE_TRANSITION.md").read_text(encoding="utf-8")
        for name in ("simulate_competitive_to_monopoly.py", "report_competitive_to_monopoly.py",
                     "report_competitive_main_comparison.py"):
            self.assertIn(f"scripts/{name}", guide)
        implementation = (ROOT / "REPLICATION.md").read_text(encoding="utf-8")
        for detail in ("32", "log1p", "expm1", "1,001", "801", "Gauss-Legendre"):
            self.assertIn(detail, implementation)

    def test_growth_reversal_method_accompanies_the_supplementary_experiment(self):
        main = web.flatten(ROOT / "main_rewrite.tex", ROOT, [])
        supplement = web.flatten(ROOT / "online_appendix.tex", ROOT, [])
        label = r"\label{app:rewrite-growth-reversal-numerics}"
        self.assertNotIn(label, main)
        self.assertIn(label, supplement)
        self.assertNotIn(r"\ref{paper-app:rewrite-growth-reversal-numerics}", supplement)
        experiment = self.content.index('id="subsec:rewrite-monopoly-growth-reversal"')
        method = self.content.index('id="app:rewrite-growth-reversal-numerics"')
        self.assertGreater(method, experiment)
        self.assertIn('href="#app:rewrite-growth-reversal-numerics"', self.content)

    def test_accuracy_table_retains_eight_cases_without_mesh_column(self):
        table = (ROOT / "sections_rewrite/rsi_illustrative_accuracy.tex").read_text(encoding="utf-8")
        self.assertNotIn("Mesh points", table)
        rows = [line for line in table.splitlines() if re.match(r"[17]\.5 &", line)]
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(line.count(" & ") == 4 for line in rows))

    def test_textual_endpoints_and_replication_are_retained(self):
        for text in ("Advances in artificial intelligence", "Declaration of AI use",
                     "Accuracy and equilibrium checks", "Replication files", "Step 4. Reconstruction of nearby equilibria."):
            self.assertIn(text, self.content)
        self.assertIn("ref-romer1990", self.content)
        self.assertIn("Journal of Political Economy", self.content)


if __name__ == "__main__":
    unittest.main()
