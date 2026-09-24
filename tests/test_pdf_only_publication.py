"""Publication-contract tests using temporary Git snapshots, without a network."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_pdf_publication as publication


PDF_PATH = (
    "paper/the-future-of-growth-and-human-labor-under-recursive-ai-self-improvement.pdf"
)
REQUIRED_FILES = (
    "index.html",
    "web.css",
    "web.js",
    "favicon.svg",
    "generated/manuscript.html",
    "generated/manuscript-meta.json",
    "generated/simulations.json",
)


class SnapshotConfigurationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.config = Path(folder.name) / "digital-edition.json"

    def write_config(self, value):
        self.config.write_text(json.dumps(value), encoding="utf-8")

    def test_accepts_full_lowercase_commit(self):
        commit = "0123456789abcdef" * 2 + "01234567"
        self.write_config({"snapshot_commit": commit})
        self.assertEqual(publication.load_snapshot_commit(self.config), commit)

    def test_rejects_malformed_commit(self):
        for commit in (
            "",
            "main",
            "codex/digital-edition",
            "a" * 39,
            "a" * 41,
            "A" * 40,
            "g" * 40,
            " " + "a" * 40,
            "a" * 40 + "\n",
            None,
            123,
            ["a" * 40],
        ):
            with self.subTest(commit=commit):
                self.write_config({"snapshot_commit": commit})
                with self.assertRaises(ValueError):
                    publication.load_snapshot_commit(self.config)

    def test_rejects_missing_field_and_non_object_configuration(self):
        for value in ({}, {"commit": "a" * 40}, [], None, "a" * 40):
            with self.subTest(value=value):
                self.write_config(value)
                with self.assertRaises(ValueError):
                    publication.load_snapshot_commit(self.config)

    def test_rejects_invalid_json(self):
        self.config.write_text('{"snapshot_commit":', encoding="utf-8")
        with self.assertRaises(ValueError):
            publication.load_snapshot_commit(self.config)


class PdfOnlyPublicationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.snapshot = self.root / "snapshot"
        self.snapshot.mkdir()
        self.output = self.root / "site"
        self.pdf = self.root / "current.pdf"
        self.pdf.write_bytes(b"%PDF-1.7\nnew manuscript bytes\n%%EOF\n")
        self.files = {
            "index.html": b"<!doctype html>\r\n<title>Approved edition</title>\r\n",
            "web.css": b"body { color: #123; }\n",
            "web.js": b"const edition = 'approved';\n",
            "favicon.svg": b"<svg xmlns='http://www.w3.org/2000/svg'/>\n",
            "generated/manuscript.html": b"<article>Approved text</article>\n",
            "generated/manuscript-meta.json": b'{"source_sha256":"approved"}\n',
            "generated/simulations.json": b'{"datasets":{}}\n',
            "generated/assets/figure.svg": b"<svg><text>Approved figure</text></svg>\n",
            "generated/assets/nested/figure data.bin": b"\x00\xff\x0a\x0d\x80",
            ".nojekyll": b"",
            "other/download.pdf": b"%PDF-1.4\nother PDF must not change\n",
            PDF_PATH: b"%PDF-1.4\nprevious manuscript\n%%EOF\n",
        }
        self.git("init", "--quiet")
        self.git("config", "user.name", "Publication Contract Test")
        self.git("config", "user.email", "publication-test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "core.hooksPath", str(self.root / "no-hooks"))
        for relative, content in self.files.items():
            path = self.snapshot / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.commit = self.commit_snapshot()

    def git(self, *args):
        result = subprocess.run(
            ["git", "-C", str(self.snapshot), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return result.stdout.strip()

    def commit_snapshot(self):
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", "Approved digital snapshot")
        return self.git("rev-parse", "HEAD")

    def tree_bytes(self, folder):
        return {
            path.relative_to(folder).as_posix(): path.read_bytes()
            for path in folder.rglob("*")
            if path.is_file() and ".git" not in path.relative_to(folder).parts
        }

    def stage(self, expected_commit=None):
        return publication.stage_site(
            self.snapshot, self.pdf, self.output, expected_commit or self.commit
        )

    def test_replaces_only_exact_stable_pdf_and_preserves_all_other_bytes(self):
        count = self.stage()
        expected = dict(self.files)
        expected[PDF_PATH] = self.pdf.read_bytes()
        self.assertEqual(self.tree_bytes(self.output), expected)
        self.assertEqual(count, len(self.files) - 1)
        self.assertFalse((self.output / ".git").exists())

    def test_does_not_modify_snapshot_or_input_pdf(self):
        original_files = self.tree_bytes(self.snapshot)
        original_pdf = self.pdf.read_bytes()
        original_status = self.git("status", "--porcelain")
        self.stage()
        self.assertEqual(self.tree_bytes(self.snapshot), original_files)
        self.assertEqual(self.pdf.read_bytes(), original_pdf)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.commit)
        self.assertEqual(self.git("status", "--porcelain"), original_status)

    def test_exports_committed_bytes_not_dirty_or_untracked_checkout_files(self):
        (self.snapshot / "index.html").write_bytes(b"Unapproved working-tree edit")
        (self.snapshot / "untracked.txt").write_bytes(b"Unapproved new file")
        original_files = self.tree_bytes(self.snapshot)
        count = self.stage()
        self.assertEqual((self.output / "index.html").read_bytes(), self.files["index.html"])
        self.assertFalse((self.output / "untracked.txt").exists())
        self.assertEqual(self.tree_bytes(self.snapshot), original_files)
        self.assertEqual(count, len(self.files) - 1)

    def test_rejects_snapshot_head_different_from_pinned_commit(self):
        different_commit = "0" * 40 if self.commit != "0" * 40 else "1" * 40
        with self.assertRaises(ValueError):
            self.stage(different_commit)

    def test_rejects_missing_required_site_file(self):
        for relative in REQUIRED_FILES:
            with self.subTest(relative=relative):
                path = self.snapshot / relative
                path.unlink()
                self.commit = self.commit_snapshot()
                self.output = self.root / ("missing-" + relative.replace("/", "-"))
                with self.assertRaises(ValueError):
                    self.stage()
                path.write_bytes(self.files[relative])
                self.commit = self.commit_snapshot()

    def test_rejects_snapshot_without_generated_svg_assets(self):
        (self.snapshot / "generated/assets/figure.svg").unlink()
        self.commit = self.commit_snapshot()
        with self.assertRaises(ValueError):
            self.stage()

    def test_rejects_invalid_pdf(self):
        for index, content in enumerate((b"", b"not a PDF", b"<html>Build error</html>")):
            with self.subTest(content=content):
                self.pdf.write_bytes(content)
                self.output = self.root / f"invalid-pdf-{index}"
                with self.assertRaises(ValueError):
                    self.stage()

    def test_accepts_existing_empty_output_directory(self):
        self.output.mkdir()
        self.assertEqual(self.stage(), len(self.files) - 1)

    def test_rejects_nonempty_output_without_overwriting_existing_content(self):
        self.output.mkdir()
        sentinel = self.output / "already-published.txt"
        sentinel.write_bytes(b"Existing output must be preserved")
        original = self.tree_bytes(self.output)
        with self.assertRaises(ValueError):
            self.stage()
        self.assertEqual(self.tree_bytes(self.output), original)


if __name__ == "__main__":
    unittest.main()
