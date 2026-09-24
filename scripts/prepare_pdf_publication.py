"""Publish a new PDF while preserving every other byte of an approved site."""

import argparse
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile


PDF_PATH = "paper/the-future-of-growth-and-human-labor-under-recursive-ai-self-improvement.pdf"
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


def stage_site(snapshot: Path, pdf: Path, output: Path, expected_commit: str) -> int:
    """Export a pinned Git snapshot and replace only its stable public PDF."""
    head = subprocess.check_output(
        ["git", "-C", str(snapshot), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != expected_commit:
        raise ValueError("Snapshot HEAD does not match the approved digital edition.")
    with pdf.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("The replacement file is not a PDF.")
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

    destination = output / PDF_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(pdf, destination)
    expected_files = set(original) | {PDF_PATH}
    actual_files = {
        path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()
    }
    if actual_files != expected_files:
        raise ValueError("Publication unexpectedly added or removed site files.")
    for name, content in original.items():
        if name != PDF_PATH and (output / name).read_bytes() != content:
            raise ValueError(f"Digital edition changed unexpectedly: {name}")
    if destination.read_bytes() != pdf.read_bytes():
        raise ValueError("The public PDF does not match the new compilation.")
    return len(expected_files - {PDF_PATH})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["ref", "stage"])
    parser.add_argument("--config", type=Path, default=Path("DIGITAL_EDITION.json"))
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    commit = load_snapshot_commit(args.config)
    if args.command == "ref":
        print(commit)
        return
    if any(value is None for value in (args.snapshot, args.pdf, args.output)):
        parser.error("stage requires --snapshot, --pdf, and --output")
    count = stage_site(args.snapshot, args.pdf, args.output, commit)
    print(f"Updated only the stable PDF; all {count} digital-edition files are byte-identical.")


if __name__ == "__main__":
    main()
