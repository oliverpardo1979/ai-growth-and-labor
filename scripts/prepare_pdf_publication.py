"""Publish paper PDFs without rebuilding the approved digital edition."""

import argparse
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile


PDF_PATH = "paper/the-future-of-growth-and-human-labor-under-recursive-ai-self-improvement.pdf"
SUPPLEMENT_PATH = "paper/online-appendix.pdf"
# Narrow author-approved additions: download links, not a new HTML manuscript.
SUPPLEMENT_LINKS = (
    (
        '<a class="button secondary" href="#explore">Explore the simulations →</a>',
        f'<a class="button secondary" href="{SUPPLEMENT_PATH}">Online appendix PDF ↗</a>',
    ),
    (
        f'<a class="text-link" href="{PDF_PATH}">Download the typeset PDF ↗</a>',
        f'<a class="text-link" href="{SUPPLEMENT_PATH}">Online appendix PDF ↗</a>',
    ),
)
REQUIRED = {
    "index.html", "web.css", "web.js", "favicon.svg",
    "generated/manuscript.html", "generated/manuscript-meta.json",
    "generated/simulations.json",
}


def load_snapshot_commit(config_path: Path) -> str:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Digital-edition configuration must be a JSON object.")
    commit = config.get("snapshot_commit", "")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Digital edition must be pinned to a full immutable commit SHA.")
    return commit


def add_supplement_links(index: bytes) -> bytes:
    """Insert only the two approved links; preserve all other HTML bytes."""
    for anchor, link in SUPPLEMENT_LINKS:
        anchor, link = anchor.encode("utf-8"), link.encode("utf-8")
        if anchor + link in index:
            continue
        if index.count(anchor) != 1 or link in index:
            raise ValueError("Cannot locate the approved online-appendix link position.")
        index = index.replace(anchor, anchor + link, 1)
    return index


def stage_site(
    snapshot: Path, pdf: Path, output: Path, expected_commit: str,
    supplement: Path | None = None,
) -> int:
    """Export the pinned site and update PDFs plus approved supplement links."""
    head = subprocess.check_output(
        ["git", "-C", str(snapshot), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != expected_commit:
        raise ValueError("Snapshot HEAD does not match the approved digital edition.")
    replacements = {PDF_PATH: pdf}
    if supplement is not None:
        replacements[SUPPLEMENT_PATH] = supplement
    for source in replacements.values():
        with source.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise ValueError(f"The replacement file is not a PDF: {source.name}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Publication output must be absent or empty; nothing was overwritten.")

    archive_bytes = subprocess.check_output(
        ["git", "-C", str(snapshot), "archive", "--format=tar", "HEAD"]
    )
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        members = archive.getmembers()
        if any(not (member.isfile() or member.isdir()) for member in members):
            raise ValueError("Digital snapshot must contain regular files and directories only.")
        original = {
            member.name: archive.extractfile(member).read()
            for member in members if member.isfile()
        }
        missing = REQUIRED - original.keys()
        if missing or not any(
            name.startswith("generated/assets/") and name.endswith(".svg")
            for name in original
        ):
            raise ValueError(f"Incomplete digital snapshot; required files/assets missing: {sorted(missing)}")
        index = add_supplement_links(original["index.html"]) if supplement else None
        output.mkdir(parents=True, exist_ok=True)
        archive.extractall(output, filter="data")

    for name, source in replacements.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    if index is not None:
        (output / "index.html").write_bytes(index)
    expected_files = set(original) | set(replacements)
    actual_files = {
        path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()
    }
    if actual_files != expected_files:
        raise ValueError("Publication unexpectedly added or removed site files.")
    for name, content in original.items():
        expected_content = index if name == "index.html" and index is not None else content
        if name not in replacements and (output / name).read_bytes() != expected_content:
            raise ValueError(f"Digital edition changed unexpectedly: {name}")
    for name, source in replacements.items():
        if (output / name).read_bytes() != source.read_bytes():
            raise ValueError(f"The public PDF does not match the new compilation: {name}")
    changed = set(replacements) | ({"index.html"} if index is not None else set())
    return len(expected_files - changed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["ref", "stage"])
    parser.add_argument("--config", type=Path, default=Path("DIGITAL_EDITION.json"))
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--supplement", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    commit = load_snapshot_commit(args.config)
    if args.command == "ref":
        print(commit)
        return
    if any(value is None for value in (args.snapshot, args.pdf, args.output)):
        parser.error("stage requires --snapshot, --pdf, and --output")
    count = stage_site(args.snapshot, args.pdf, args.output, commit, args.supplement)
    updated = "the paper PDFs and approved supplement links" if args.supplement else "the stable PDF"
    print(f"Updated only {updated}; all {count} other digital-edition files are byte-identical.")


if __name__ == "__main__":
    main()
