#!/usr/bin/env python3
"""Build the complete web manuscript from active LaTeX and compiled metadata.

Dependencies: Pandoc >= 3, PyMuPDF, beautifulsoup4.  A completed LaTeX build
must supply main_rewrite.aux, main_rewrite.bbl and main_rewrite.pdf together.
Install Python dependencies with ``pip install pymupdf beautifulsoup4``;
``pypandoc_binary`` optionally supplies Pandoc. No network is used by this
script. Source text is not rewritten and inactive/commented material is not
published. The compiled bibliography and labels, rather than a new citation
style or independently guessed numbering, are authoritative.

Typical use after latexmk:
    python scripts/build_web_manuscript.py --build-dir .
Local checkout with the PDF under output/pdf:
    python scripts/build_web_manuscript.py --build-dir output/pdf

Output is an HTML fragment for insertion into docs/index.html; asset URLs
are relative to that page, not to the fragment's storage directory.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
# Optional, gitignored installation for the desktop's isolated Python runtime.
if (ROOT / "tmp/web-build-deps").is_dir():
    sys.path.insert(0, str(ROOT / "tmp/web-build-deps"))


class ConversionError(RuntimeError):
    """A construct or discrepancy that must not be silently omitted."""


def group(text: str, pos: int, opening: str = "{", closing: str = "}") -> tuple[str, int]:
    """Read a balanced TeX group, including nested groups and escaped braces."""
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] != opening:
        raise ConversionError(f"Expected {opening!r} near {text[pos:pos + 70]!r}")
    start, depth = pos + 1, 1
    pos += 1
    while pos < len(text):
        if text[pos] == "\\":
            # An escaped delimiter is not a group delimiter; control words
            # can be skipped character by character without changing depth.
            if pos + 1 < len(text) and text[pos + 1] in "{}[]%\\":
                pos += 2
                continue
        if text[pos] == opening:
            depth += 1
        elif text[pos] == closing:
            depth -= 1
            if not depth:
                return text[start:pos], pos + 1
        pos += 1
    raise ConversionError("Unterminated TeX group")


def groups(text: str) -> list[str]:
    result, pos = [], 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
        else:
            item, pos = group(text, pos)
            result.append(item)
    return result


def strip_comments(text: str) -> str:
    """Honor TeX's escaped percent signs and literal verbatim environments."""
    result, literal = [], False
    for line in text.splitlines(keepends=True):
        if r"\begin{verbatim}" in line:
            literal = True
        if literal:
            result.append(line)
            if r"\end{verbatim}" in line:
                literal = False
            continue
        if not line.strip():
            # A physically empty TeX line inserts a paragraph break even
            # when the preceding comment suppressed that line's end token.
            result.append("\n\n")
            continue
        cut = None
        for i, ch in enumerate(line):
            if ch == "%":
                backslashes, j = 0, i - 1
                while j >= 0 and line[j] == "\\":
                    backslashes += 1
                    j -= 1
                if backslashes % 2 == 0:
                    cut = i
                    break
        # A TeX comment suppresses its line ending too, not the next line.
        result.append(line if cut is None else line[:cut])
    if literal:
        raise ConversionError("Unterminated verbatim environment")
    return "".join(result)


def flatten(path: Path, root: Path, seen: list[Path], stack: tuple[Path, ...] = ()) -> str:
    path = path.resolve()
    if path in stack:
        raise ConversionError(f"Cyclic input: {path}")
    if not path.is_relative_to(root.resolve()):
        raise ConversionError(f"Input escapes manuscript directory: {path}")
    seen.append(path)
    source = strip_comments(path.read_text(encoding="utf-8"))

    def replace(match: re.Match[str]) -> str:
        target = root / match.group(1)
        if not target.suffix:
            target = target.with_suffix(".tex")
        if not target.is_file():
            raise ConversionError(f"Missing active input: {target}")
        return "\n" + flatten(target, root, seen, stack + (path,)) + "\n"

    return re.sub(r"\\(?:input|include)\s*\{([^}]+)\}", replace, source)


def read_aux(path: Path) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    labels, citations = {}, {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(r"\newlabel{"):
            key, pos = group(line, len(r"\newlabel"))
            value, _ = group(line, pos)
            fields = groups(value)
            if key in labels:
                raise ConversionError(f"Duplicate compiled label: {key}")
            labels[key] = {"number": fields[0].strip("{}"), "page": fields[1],
                           "title": fields[2], "destination": fields[3]}
        elif line.startswith(r"\bibcite{"):
            key, pos = group(line, len(r"\bibcite"))
            value, _ = group(line, pos)
            fields = groups(value)
            citations[key] = {"year": fields[1], "author": fields[2].strip("{}")}
    if not labels or not citations:
        raise ConversionError("Compiled AUX is missing labels or bibliography metadata")
    return labels, citations


def find_pandoc(explicit: str | None = None) -> str:
    candidates = [explicit, os.environ.get("PANDOC"), shutil.which("pandoc")]
    candidates.extend(str(path) for path in (ROOT / "tmp").glob("**/pandoc.exe"))
    try:
        import pypandoc
        candidates.append(pypandoc.get_pandoc_path())
    except (ImportError, OSError):
        pass
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise ConversionError("Pandoc not found; install Pandoc 3 or pypandoc_binary, or pass --pandoc")


class Pandoc:
    def __init__(self, executable: str, root: Path):
        self.executable, self.root = executable, root
        self.warnings: list[str] = []

    def run(self, text: str, source: str, target: str, *args: str) -> str:
        proc = subprocess.run([self.executable, "-f", source, "-t", target, *args],
                              input=text, capture_output=True, encoding="utf-8", cwd=self.root)
        if proc.returncode:
            raise ConversionError(f"Pandoc failed: {proc.stderr}")
        if proc.stderr.strip():
            self.warnings.append(proc.stderr.strip())
        return proc.stdout

    def ast(self, text: str) -> dict[str, Any]:
        return json.loads(self.run(text, "latex+raw_tex", "json"))

    def fragment(self, text: str) -> str:
        return self.run(text, "latex", "html5", "--mathjax", "--wrap=none").strip()

    def plain(self, text: str) -> str:
        return self.run(text, "latex", "plain", "--wrap=none").strip()


def command_rewrite(source: str, command: str, callback: Any) -> str:
    pattern = re.compile(r"\\" + re.escape(command) + r"(?![A-Za-z])")
    result, pos = [], 0
    for match in pattern.finditer(source):
        if match.start() < pos:
            continue
        value, end = group(source, match.end())
        result.append(source[pos:match.start()])
        result.append(callback(value))
        pos = end
    result.append(source[pos:])
    return "".join(result)


def environment_end(source: str, start: int, name: str) -> tuple[str, int]:
    opening = re.match(r"\\begin\{" + re.escape(name) + r"\}", source[start:])
    if not opening:
        raise ConversionError(f"Missing opening environment {name}")
    body_start, depth = start + opening.end(), 1
    pattern = re.compile(r"\\(begin|end)\{" + re.escape(name) + r"\}")
    for token in pattern.finditer(source, body_start):
        depth += 1 if token.group(1) == "begin" else -1
        if not depth:
            return source[body_start:token.start()], token.end()
    raise ConversionError(f"Unclosed environment: {name}")


def split_math_rows(source: str) -> list[str]:
    """Split top-level AMS rows without splitting matrices or grouped math."""
    result, start, pos, depth, environments = [], 0, 0, 0, []
    while pos < len(source):
        token = re.match(r"\\(begin|end)\{([^}]+)\}", source[pos:])
        if token:
            if token.group(1) == "begin":
                environments.append(token.group(2))
            elif environments:
                environments.pop()
            pos += token.end()
            continue
        if source.startswith("\\\\", pos) and depth == 0 and not environments:
            result.append(source[start:pos])
            pos += 2
            # Optional inter-row spacing has no semantic content.
            if pos < len(source) and source[pos] == "[":
                _, pos = group(source, pos, "[", "]")
            start = pos
            continue
        if source[pos] == "\\" and pos + 1 < len(source) and source[pos + 1] in "{}":
            pos += 2
            continue
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
        pos += 1
    result.append(source[start:])
    return result


class EquationNumbering:
    def __init__(self, labels: dict[str, dict[str, str]]):
        self.labels, self.counter, self.numbered_rows = labels, 0, 0
        self.checked_labels: set[str] = set()

    def validate(self, source: str, number: str) -> None:
        for label in re.findall(r"\\label\{([^}]+)\}", source):
            if label not in self.labels or self.labels[label]["number"] != number:
                actual = self.labels.get(label, {}).get("number", "MISSING")
                raise ConversionError(f"Equation numbering mismatch for {label}: source {number}, AUX {actual}")
            self.checked_labels.add(label)

    def apply(self, source: str, sub: dict[str, Any] | None = None) -> str:
        pattern = re.compile(r"\\begin\{(subequations|equation\*?|align\*?|gather\*?)\}")
        result, pos = [], 0
        while match := pattern.search(source, pos):
            name = match.group(1)
            body, end = environment_end(source, match.start(), name)
            result.append(source[pos:match.start()])
            if name == "subequations":
                if sub is not None:
                    raise ConversionError("Nested subequations are unsupported")
                self.counter += 1
                parent = str(self.counter)
                before_inner = re.split(r"\\begin\{", body, maxsplit=1)[0]
                self.validate(before_inner, parent)
                # Pandoc need not understand the wrapper; its parent label stays.
                result.append(self.apply(body, {"parent": parent, "row": 0}))
            elif name.endswith("*"):
                result.append(source[match.start():end])
            else:
                rows = split_math_rows(body) if name in ("align", "gather") else [body]
                tagged = []
                for row in rows:
                    if not row.strip():
                        continue
                    if not re.search(r"\\(?:nonumber|notag)\b", row):
                        if sub is None:
                            self.counter += 1
                            number = str(self.counter)
                        else:
                            sub["row"] += 1
                            if sub["row"] > 26:
                                raise ConversionError("More than 26 subequations")
                            number = sub["parent"] + chr(96 + sub["row"])
                        self.validate(row, number)
                        row = row.rstrip() + r"\tag{" + number + "}"
                        self.numbered_rows += 1
                    tagged.append(row)
                result.append(r"\begin{" + name + "}\n" + "\\\\\n".join(tagged) + r"\end{" + name + "}")
            pos = end
        result.append(source[pos:])
        return "".join(result)


def prepare_theorems(source: str, labels: dict[str, dict[str, str]]) -> str:
    pattern = re.compile(r"\\begin\{(proposition|corollary|lemma|definition|assumption|remark)\}")
    counters: dict[str, int] = {}
    result, pos = [], 0
    for match in pattern.finditer(source):
        kind, end = match.group(1), match.end()
        while end < len(source) and source[end].isspace():
            end += 1
        title = ""
        if source[end:end + 1] == "[":
            title, end = group(source, end, "[", "]")
        counters[kind] = counters.get(kind, 0) + 1
        number = str(counters[kind])
        first_label = re.match(r"\s*\\label\{([^}]+)\}", source[end:])
        if first_label:
            key = first_label.group(1)
            if key not in labels or labels[key]["number"] != number:
                raise ConversionError(f"Theorem numbering mismatch: {key}, expected {number}")
        heading = f"{kind.capitalize()} {number}" + (f" ({title})" if title else "") + "."
        result.extend([source[pos:match.start()], r"\begin{quote}", "\n\\textbf{" + heading + "}\n\n"])
        pos = end
    result.append(source[pos:])
    return re.sub(r"\\end\{(?:proposition|corollary|lemma|definition|assumption|remark)\}", r"\\end{quote}", "".join(result))


def prepare_citations(source: str, citations: dict[str, dict[str, str]]) -> tuple[str, set[str]]:
    pattern = re.compile(r"\\(citep|citet|cite)(?![A-Za-z])")
    result, pos, used = [], 0, set()
    for match in pattern.finditer(source):
        end, options = match.end(), []
        while source[end:end + 1] == "[":
            value, end = group(source, end, "[", "]")
            options.append(value)
        keys, end = group(source, end)
        prefix, suffix = (options[0], options[1]) if len(options) == 2 else ("", options[0] if options else "")
        if len(options) > 2:
            raise ConversionError("More than two citation optional arguments")
        rendered = []
        for key in [part.strip() for part in keys.split(",")]:
            if key not in citations:
                raise ConversionError(f"Citation absent from compiled AUX: {key}")
            used.add(key)
            item = citations[key]
            value = item["author"] + (" (" + item["year"] + ")" if match.group(1) == "citet" else ", " + item["year"])
            rendered.append(r"\hyperlink{ref-" + key + "}{" + value + "}")
        text = "; ".join(rendered)
        if prefix:
            text = prefix + " " + text
        if suffix:
            if match.group(1) == "citet" and len(rendered) == 1:
                text = text[:-2] + ", " + suffix + ")}"  # append inside linked year parentheses
            else:
                text += ", " + suffix
        if match.group(1) != "citet":
            text = "(" + text + ")"
        result.extend([source[pos:match.start()], text])
        pos = end
    result.append(source[pos:])
    return "".join(result), used


def read_bibliography(path: Path) -> list[tuple[str, str]]:
    source = strip_comments(path.read_text(encoding="utf-8"))
    pattern = re.compile(r"\\bibitem(?:\[[\s\S]*?\])?\{([^}]+)\}")
    items = list(pattern.finditer(source))
    result = []
    for i, match in enumerate(items):
        end = items[i + 1].start() if i + 1 < len(items) else source.index(r"\end{thebibliography}")
        entry = source[match.end():end].strip().replace(r"\newblock", " ")
        result.append((match.group(1), entry))
    if not result:
        raise ConversionError("Empty compiled bibliography")
    return result


def extract_figures(source: str, root: Path, pdf: Path, assets: Path,
                    labels: dict[str, dict[str, str]], asset_prefix: str) -> tuple[str, list[dict[str, Any]]]:
    try:
        import pymupdf as fitz
    except ImportError as exc:
        raise ConversionError("PyMuPDF is required: pip install pymupdf") from exc
    assets.mkdir(parents=True, exist_ok=True)
    manuscript = fitz.open(pdf)
    pattern = re.compile(r"\\begin\{figure\}")
    result, figures, pos = [], [], 0
    while match := pattern.search(source, pos):
        body, end = environment_end(source, match.start(), "figure")
        label_matches = re.findall(r"\\label\{([^}]+)\}", body)
        if len(label_matches) != 1 or label_matches[0] not in labels:
            raise ConversionError("Every figure must have exactly one compiled label")
        key = label_matches[0]
        cap = re.search(r"\\caption\s*", body)
        if not cap:
            raise ConversionError(f"Figure without caption: {key}")
        caption, _ = group(body, cap.end())
        number = labels[key]["number"]
        filename = key.replace(":", "-") + ".svg"
        info: dict[str, Any] = {"id": key, "number": number, "asset": f"{asset_prefix}/{filename}"}
        if r"\begin{tikzpicture}" in body:
            page_index = int(labels[key]["page"]) - 1
            page = manuscript[page_index]
            captions = page.search_for(f"Figure {number}:")
            if len(captions) != 1:
                raise ConversionError(f"Cannot locate unique PDF caption for {key}")
            caption_top = captions[0].y0
            drawings = [drawing["rect"] for drawing in page.get_drawings()
                        if drawing["rect"].height > 8 and drawing["rect"].width > 10
                        and drawing["rect"].y1 < caption_top]
            if not drawings:
                raise ConversionError(f"No vector diagram found above caption: {key}")
            clip = fitz.Rect(drawings[0])
            for rect in drawings[1:]:
                clip |= rect
            initial = fitz.Rect(clip)
            for block in page.get_text("blocks"):
                rect = fitz.Rect(block[:4])
                if (rect.y1 >= initial.y0 - 2 and rect.y0 <= initial.y1 + 24
                        and rect.y1 < caption_top - 5 and rect.x1 >= initial.x0 - 25
                        and rect.x0 <= initial.x1 + 25):
                    clip |= rect
            clip += (-5, -5, 5, 5)
            clip.y1 = min(clip.y1, caption_top - 5)
            if clip.width < 80 or clip.height < 40 or clip.y0 < 0:
                raise ConversionError(f"Implausible diagram crop for {key}: {clip}")
            cropped = fitz.open()
            target = cropped.new_page(width=clip.width, height=clip.height)
            target.show_pdf_page(target.rect, manuscript, page_index, clip=clip)
            svg = target.get_svg_image(text_as_path=True)
            qa_dir = root / "tmp/web-manuscript-qa"
            qa_dir.mkdir(parents=True, exist_ok=True)
            target.get_pixmap(matrix=fitz.Matrix(2, 2)).save(qa_dir / filename.replace(".svg", ".png"))
            info.update({"kind": "tikz-pdf-crop", "pdf_page": page_index + 1, "crop": list(clip)})
            cropped.close()
        else:
            image = re.search(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", body)
            if not image:
                raise ConversionError(f"Unsupported figure content: {key}")
            figure_path = (root / image.group(1)).resolve()
            if not figure_path.is_relative_to(root.resolve()):
                raise ConversionError("Figure path escapes repository")
            document = fitz.open(figure_path)
            if len(document) != 1:
                raise ConversionError(f"Expected one-page simulation figure: {figure_path}")
            svg = document[0].get_svg_image(text_as_path=True)
            info.update({"kind": "pdf-figure", "source": figure_path.relative_to(root).as_posix()})
            document.close()
        (assets / filename).write_text(svg, encoding="utf-8")
        figures.append(info)
        # Let Pandoc retain the mathematical caption, then number it in AST.
        replacement = (r"\begin{figure}\centering\includegraphics{" + info["asset"] + "}"
                       + r"\caption{" + caption + r"}\label{" + key + r"}\end{figure}")
        result.extend([source[pos:match.start()], replacement])
        pos = end
    result.append(source[pos:])
    manuscript.close()
    return "".join(result), figures


def inlines_text(nodes: Any) -> str:
    if isinstance(nodes, list):
        return "".join(inlines_text(node) for node in nodes)
    if not isinstance(nodes, dict):
        return ""
    kind, value = nodes.get("t"), nodes.get("c")
    if kind == "Str":
        return value
    if kind in ("Space", "SoftBreak", "LineBreak"):
        return " "
    if kind == "Math":
        return value[1]
    if kind in ("Span", "Link", "Image"):
        return inlines_text(value[1])
    return inlines_text(value)


def transform_ast(document: dict[str, Any], labels: dict[str, dict[str, str]],
                  table_labels: list[str] | None = None,
                  heading_numbers: dict[tuple[int, str], str] | None = None) -> list[dict[str, Any]]:
    sections = []
    pending_tables = iter(table_labels or [])
    table_keys = set(table_labels or [])
    unsupported: set[str] = set()
    # Literal source paths are code, not URLs or executable TeX. Support the
    # brace form used in the manuscript; leave other constructs fail-closed.
    literal_path = re.compile(r"\\path\{([^{}\r\n]*)\}")

    def inspect_raw(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("t") in ("RawInline", "RawBlock") and value["c"][0] in ("latex", "tex"):
                raw = value["c"][1]
                if not (re.fullmatch(r"\\(?:label|ref|eqref)\*?\{[^}]+\}", raw)
                        or literal_path.fullmatch(raw)):
                    unsupported.add(raw)
            for child in value.values():
                inspect_raw(child)
        elif isinstance(value, list):
            for child in value:
                inspect_raw(child)

    inspect_raw(document)
    if unsupported:
        raise ConversionError("Unsupported raw TeX retained by Pandoc:\n" + "\n".join(sorted(unsupported)))

    def visit(node: Any) -> Any:
        if isinstance(node, list):
            return [visit(item) for item in node]
        if not isinstance(node, dict):
            return node
        kind, content = node.get("t"), node.get("c")
        if kind in ("RawInline", "RawBlock") and content[0] in ("latex", "tex"):
            path = literal_path.fullmatch(content[1])
            if path:
                inline = {"t": "Code", "c": [["", [], []], path.group(1)]}
                return {"t": "Plain", "c": [inline]} if kind == "RawBlock" else inline
            raw = re.fullmatch(r"\\(label|ref|eqref)\*?\{([^}]+)\}", content[1])
            if not raw or raw.group(2) not in labels:
                raise ConversionError(f"Unsupported raw TeX or absent label: {content[1][:180]}")
            command, key = raw.groups()
            if command == "label":
                if key in table_keys:
                    return {"t": "Plain", "c": []} if kind == "RawBlock" else {"t": "Str", "c": ""}
                inline = {"t": "Span", "c": [[key, ["source-anchor"], []], []]}
            else:
                number = labels[key]["number"]
                if command == "eqref":
                    number = "(" + number + ")"
                inline = {"t": "Link", "c": [["", [], []], [{"t": "Str", "c": number}], ["#" + key, ""]]}
            return {"t": "Plain", "c": [inline]} if kind == "RawBlock" else inline
        if kind == "Header":
            level, attrs, title = content
            key = attrs[0]
            number = labels.get(key, {}).get("number", "")
            if not number and heading_numbers:
                number = heading_numbers.get((level, inlines_text(title)), "")
            if key in labels and not labels[key]["destination"].startswith(("section.", "subsection.", "subsubsection.", "appendix.")):
                raise ConversionError(f"Header label has unexpected target: {key}")
            sections.append({"id": key, "title": inlines_text(title), "level": level, "number": number})
            if number:
                content[2] = [{"t": "Span", "c": [["", ["section-number"], []], [{"t": "Str", "c": number}]]},
                              {"t": "Space"}] + title
        elif kind == "Link":
            attrs, _, target = content
            data = dict(attrs[2])
            if "reference" in data:
                key = data["reference"]
                if key not in labels:
                    raise ConversionError(f"Reference missing from AUX: {key}")
                number = labels[key]["number"]
                if data.get("reference-type") == "eqref":
                    number = "(" + number + ")"
                content[1] = [{"t": "Str", "c": number}]
                content[2] = ["#" + key, target[1]]
        elif kind == "Math":
            math_type, value = content
            math_labels = re.findall(r"\\label\{([^}]+)\}", value)
            content[1] = re.sub(r"\\label\{[^}]+\}", "", value)
            if math_labels:
                anchors = [{"t": "Span", "c": [[label, ["equation-anchor"], []], []]} for label in math_labels]
                return {"t": "Span", "c": [["", ["manuscript-equation"], []], anchors + [node]]}
        elif kind in ("Span", "Div") and content[0][0] in table_keys:
            content[0][0] = ""
        elif kind == "BlockQuote" and content and content[0].get("t") == "Para":
            first = content[0]["c"]
            heading = inlines_text(first[0]) if first and first[0].get("t") == "Strong" else ""
            theorem = re.match(r"(Proposition|Corollary|Lemma|Definition|Assumption|Remark) \d+", heading)
            if theorem:
                return {"t": "Div", "c": [["", ["theorem", theorem.group(1).lower()], []], visit(content)]}
        elif kind == "Figure":
            attrs, caption, _ = content
            key = attrs[0]
            if key not in labels:
                raise ConversionError(f"Figure missing compiled number: {key}")
            for block in caption[1]:
                if block["t"] in ("Plain", "Para"):
                    block["c"] = [{"t": "Strong", "c": [{"t": "Str", "c": "Figure " + labels[key]["number"] + ":"}]}, {"t": "Space"}] + block["c"]
                    break
        elif kind == "Table":
            attrs, caption = content[:2]
            key = next(pending_tables, "")
            if not key or key not in labels:
                raise ConversionError(f"Table missing compiled label: {key}")
            attrs[0] = key
            for block in caption[1]:
                if block["t"] in ("Plain", "Para"):
                    block["c"] = [{"t": "Strong", "c": [{"t": "Str", "c": "Table " + labels[key]["number"] + ":"}]}, {"t": "Space"}] + block["c"]
                    break
        if "c" in node:
            node["c"] = visit(node["c"])
        return node

    document["blocks"] = visit(document["blocks"])
    return sections


def clean_layout(source: str) -> str:
    # Layout has no counterpart in a reflowable article. Explicitly consume
    # known arguments so a generic parser cannot swallow following prose.
    for command in ("Needspace", "setstretch", "setcounter", "setlength", "addcontentsline", "vspace"):
        count = {"setcounter": 2, "setlength": 2, "addcontentsline": 3}.get(command, 1)
        for _ in range(count):
            if _ == 0:
                source = command_rewrite(source, command, lambda value: r"\WEBREMOVE" if count > 1 else "")
            else:
                source = command_rewrite(source, "WEBREMOVE", lambda value: r"\WEBREMOVE" if _ < count - 1 else "")
    source = command_rewrite(source, "tikzset", lambda value: "")
    source = re.sub(r"\\(?:clearpage|newpage|onehalfspacing|singlespacing|phantomsection|tableofcontents|maketitle|begingroup|endgroup|appendix|small|footnotesize|centering|medskip|smallskip|noindent)\b", "", source)
    source = re.sub(r"\\bibliographystyle\{[^}]+\}|\\bibliography\{[^}]+\}", "", source)
    # minipage is layout only; keep all its contents.
    source = re.sub(r"\\begin\{minipage\}(?:\[[^]]*\])?\{[^}]+\}", "", source)
    source = source.replace(r"\end{minipage}", "")
    # The manuscript's P columns differ from p only in ragged-right layout.
    source = re.sub(r"P(?=\{[\d.]+\\textwidth\})", "p", source)
    return source


def compiled_headings(aux: Path, pandoc: Pandoc) -> dict[tuple[int, str], str]:
    """Recover numbering even for section headings without explicit labels."""
    headings = {}
    for line in aux.read_text(encoding="utf-8").splitlines():
        if not line.startswith(r"\@writefile{toc}"):
            continue
        match = re.search(r"\\contentsline\s*", line)
        if not match:
            continue
        kind, pos = group(line, match.end())
        if kind not in ("section", "subsection", "subsubsection"):
            continue
        content, _ = group(line, pos)
        numberline = re.match(r"\\numberline\s*", content)
        if not numberline:
            continue
        number, pos = group(content, numberline.end())
        title = pandoc.plain(content[pos:])
        key = (("section", "subsection", "subsubsection").index(kind) + 1, title)
        if key in headings:
            raise ConversionError(f"Ambiguous compiled heading title: {title}")
        headings[key] = number
    return headings


def verify_freshness(inputs: list[Path], build_dir: Path, bibliography: Path) -> None:
    latest = max(inputs, key=lambda path: path.stat().st_mtime)
    for suffix in ("aux", "pdf"):
        compiled = build_dir / f"main_rewrite.{suffix}"
        if compiled.stat().st_mtime + 2 < latest.stat().st_mtime:
            raise ConversionError(f"Stale {compiled.name}: recompile after changing {latest.name}")
    if (build_dir / "main_rewrite.bbl").stat().st_mtime + 2 < bibliography.stat().st_mtime:
        raise ConversionError("Compiled bibliography predates references.bib; rerun BibTeX and LaTeX")


def ast_text_tokens(value: Any) -> list[str]:
    """Visible non-mathematical tokens, excluding AST attributes and images."""
    if isinstance(value, list):
        return [token for child in value for token in ast_text_tokens(child)]
    if not isinstance(value, dict):
        return []
    kind, content = value.get("t"), value.get("c")
    if kind in ("Math", "Image"):
        return []
    if kind == "Str":
        return re.findall(r"\w+", content)
    if kind in ("Code", "CodeBlock"):
        return re.findall(r"\w+", content[1])
    return ast_text_tokens(content)


def build(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    build_dir = (root / args.build_dir).resolve()
    out_dir = (root / args.output_dir).resolve()
    for suffix in ("aux", "bbl", "pdf"):
        if not (build_dir / f"main_rewrite.{suffix}").is_file():
            raise ConversionError(f"Compile LaTeX first; missing {build_dir / ('main_rewrite.' + suffix)}")
    paths: list[Path] = []
    source = flatten(root / "main_rewrite.tex", root, paths)
    figure_inputs = [(root / name).resolve() for name in re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", source)]
    verify_freshness(paths + figure_inputs + [root / "references.bib"], build_dir, root / "references.bib")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    labels, citations = read_aux(build_dir / "main_rewrite.aux")
    active_labels = re.findall(r"\\label\{([^}]+)\}", source)
    if len(set(active_labels)) != len(active_labels):
        raise ConversionError("Duplicate labels in active LaTeX input graph")
    missing = sorted(set(active_labels) - labels.keys())
    if missing:
        raise ConversionError(f"Active labels absent from compiled AUX: {missing}")
    pandoc = Pandoc(find_pandoc(args.pandoc), root)
    meta: dict[str, Any] = {}
    for field in ("title", "author", "date"):
        match = re.search(r"\\" + field + r"\s*", source)
        if not match:
            raise ConversionError(f"Missing manuscript {field}")
        value, _ = group(source, match.end())
        meta[field] = pandoc.plain(value)
    abstract_match = re.search(r"\\begin\{abstract\}", source)
    if not abstract_match:
        raise ConversionError("Missing abstract")
    abstract, abstract_end = environment_end(source, abstract_match.start(), "abstract")
    meta["abstract"] = pandoc.plain(abstract)
    source = source[:abstract_match.start()] + source[abstract_end:]
    source = source.split(r"\begin{document}", 1)[1].rsplit(r"\end{document}", 1)[0]
    source, figures = extract_figures(source, root, build_dir / "main_rewrite.pdf", out_dir / "assets", labels, args.asset_prefix.rstrip("/"))
    source = clean_layout(source)
    source = prepare_theorems(source, labels)
    source, cited = prepare_citations(source, citations)
    numbering = EquationNumbering(labels)
    source = numbering.apply(source)
    expected_displays = len(re.findall(r"\\begin\{(?:equation|align|gather)\*?\}|\\\[", source))
    # Supply source-defined math shorthands and the table column type to the
    # reader. MathJax gets the expanded commands from Pandoc's LaTeX reader.
    preamble = (r"\newcommand{\dd}{\,\mathrm{d}}" + "\n"
                r"\newcommand{\gA}{g_A}\newcommand{\gY}{g_Y}\newcommand{\gw}{g_w}\newcommand{\sX}{s_X}" + "\n")
    ast = pandoc.ast(preamble + source)
    table_labels = []
    for table in re.finditer(r"\\begin\{table\}[\s\S]*?\\end\{table\}", source):
        keys = re.findall(r"\\label\{([^}]+)\}", table.group(0))
        if len(keys) != 1:
            raise ConversionError("Each source table must have exactly one label")
        table_labels.append(keys[0])
    sections = transform_ast(ast, labels, table_labels, compiled_headings(build_dir / "main_rewrite.aux", pandoc))
    fragment = pandoc.run(json.dumps(ast, ensure_ascii=False), "json", "html5", "--mathjax", "--wrap=none")
    abstract_html = pandoc.fragment(abstract)
    bibliography = read_bibliography(build_dir / "main_rewrite.bbl")
    bibkeys = {key for key, _ in bibliography}
    if cited != bibkeys:
        raise ConversionError(f"Compiled bibliography/citation mismatch: missing {sorted(cited - bibkeys)}, extra {sorted(bibkeys - cited)}")
    bib_html = "\n".join('<div class="csl-entry" id="ref-' + html.escape(key, quote=True) + '">'
                         + pandoc.fragment(entry) + "</div>" for key, entry in bibliography)
    result = ('<section class="manuscript-abstract" id="abstract"><h2>Abstract</h2>\n'
              + abstract_html + "\n</section>\n" + fragment
              + '<section class="manuscript-references" id="references"><h1>References</h1>\n'
              + bib_html + "\n</section>\n")
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ConversionError("beautifulsoup4 is required for output validation") from exc
    soup = BeautifulSoup(result, "html.parser")
    rendered_body = BeautifulSoup(fragment, "html.parser")
    for math in rendered_body.select(".math"):
        math.decompose()
    expected_tokens = Counter(ast_text_tokens(ast["blocks"]))
    rendered_tokens = Counter(re.findall(r"\w+", rendered_body.get_text(" ")))
    missing_tokens = expected_tokens - rendered_tokens
    if missing_tokens:
        raise ConversionError(f"Visible text lost by HTML rendering: {dict(missing_tokens)}")
    ids = [node["id"] for node in soup.select("[id]")]
    duplicates = sorted({key for key in ids if ids.count(key) > 1})
    if duplicates:
        details = [(node.name, node.get("id"), str(node)[:90]) for node in soup.select("[id]") if node["id"] in duplicates]
        raise ConversionError(f"Duplicate HTML IDs: {details}")
    absent = sorted(set(active_labels) - set(ids))
    if absent:
        raise ConversionError(f"Source labels lost during conversion: {absent}")
    broken = sorted({node["href"] for node in soup.select('a[href^="#"]') if node["href"][1:] not in ids})
    if broken:
        raise ConversionError(f"Broken internal links: {broken}")
    if len(soup.find_all("figure")) != len(figures):
        raise ConversionError("Figure count changed during conversion")
    if len(soup.select(".math.display")) != expected_displays:
        raise ConversionError("Display mathematics lost during conversion")
    if pandoc.warnings:
        raise ConversionError("Pandoc issued warnings (review before publishing):\n" + "\n".join(pandoc.warnings))
    meta.update({"schema_version": 1, "sections": sections, "source_sha256": digest,
                 "source_files": [path.relative_to(root).as_posix() for path in paths],
                 "source": "main_rewrite.tex", "figures": figures,
                 "mathjax": {"required": True, "tex_packages": ["ams"], "tags": "none"},
                 "counts": {"labels": len(active_labels), "numbered_equation_rows": numbering.numbered_rows,
                            "display_math": len(soup.select(".math.display")), "figures": len(figures),
                            "tables": len(soup.find_all("table")), "bibliography_entries": len(bibliography),
                            "citation_keys": len(cited)},
                 "validation": {"all_active_labels_present": True, "all_internal_links_resolved": True,
                                "numbering_checked_against_aux": True, "compiled_inputs_fresh": True,
                                "display_math_inventory_matches": True,
                                "visible_text_tokens_verified": sum(expected_tokens.values()),
                                "unsupported_tex": [], "pandoc_warnings": []},
                 "build_inputs": {suffix: hashlib.sha256((build_dir / f"main_rewrite.{suffix}").read_bytes()).hexdigest()
                                  for suffix in ("aux", "bbl", "pdf")}})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manuscript.html").write_text(result, encoding="utf-8")
    (out_dir / "manuscript-meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--build-dir", type=Path, default=Path("output/pdf"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs/generated"))
    parser.add_argument("--asset-prefix", default="generated/assets")
    parser.add_argument("--pandoc")
    args = parser.parse_args()
    try:
        meta = build(args)
    except (ConversionError, OSError) as exc:
        parser.exit(1, f"Web manuscript build failed: {exc}\n")
    print(json.dumps({"output": str(args.output_dir), "counts": meta["counts"], "validation": meta["validation"]}, indent=2))


if __name__ == "__main__":
    main()
