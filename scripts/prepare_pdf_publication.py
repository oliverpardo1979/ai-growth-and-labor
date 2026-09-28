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


def stage_site(
    snapshot: Path, pdf: Path, output: Path, expected_commit: str,
    supplement: Path | None = None,
) -> int:
    """Export the pinned site and update only its two downloadable PDFs."""
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
        output.mkdir(parents=True, exist_ok=True)
        archive.extractall(output, filter="data")

    for name, source in replacements.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    expected_files = set(original) | set(replacements)
    actual_files = {
        path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()
    }
    if actual_files != expected_files:
        raise ValueError("Publication unexpectedly added or removed site files.")
    for name, content in original.items():
        if name not in replacements and (output / name).read_bytes() != content:
            raise ValueError(f"Digital edition changed unexpectedly: {name}")
    for name, source in replacements.items():
        if (output / name).read_bytes() != source.read_bytes():
            raise ValueError(f"The public PDF does not match the new compilation: {name}")
    changed = set(replacements)
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
    updated = "the paper PDFs" if args.supplement else "the stable PDF"
    print(f"Updated only {updated}; all {count} other digital-edition files are byte-identical.")


if __name__ == "__main__":
    main()
