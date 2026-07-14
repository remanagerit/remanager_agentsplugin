#!/usr/bin/env python3
"""Build a deterministic, source-provenanced Hermes directory-plugin archive."""

import argparse
import gzip
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "hermes" / "reman-agentic"
SOURCE_FILES = (
    "plugin.yaml",
    "__init__.py",
    "client.py",
    "schemas.py",
    "tools.py",
    "README.md",
    "install.sh",
    "uninstall.sh",
    "skills/reman-accounting/SKILL.md",
)
LOCAL_PATH_PATTERNS = (b"/Users/", b"/home/", b"/private/tmp/", b"C:\\Users\\")


def run_git(*args):
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return result.stdout.strip()


def canonical_json(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_entry(root, path):
    relative = path.relative_to(root).as_posix()
    return {
        "path": "reman-agentic/" + relative,
        "sha256": digest(path),
        "size": path.stat().st_size,
        "mode": "0755" if path.suffix == ".sh" else "0644",
    }


def validate_source(path):
    if path.is_symlink() or not path.is_file():
        raise SystemExit(f"Hermes candidate source must be a regular file: {path}")
    content = path.read_bytes()
    if any(pattern in content for pattern in LOCAL_PATH_PATTERNS):
        raise SystemExit(f"Local filesystem path found in Hermes candidate source: {path}")


def add_tar_entry(archive, name, content, mode, mtime):
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = mode
    info.mtime = mtime
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    archive.addfile(info, io.BytesIO(content))


def build(output, allow_dirty=False):
    if not allow_dirty and run_git("status", "--porcelain"):
        raise SystemExit("Hermes release candidate requires a clean Git worktree.")

    commit = run_git("rev-parse", "HEAD")
    tree = run_git("rev-parse", "HEAD^{tree}")
    source_epoch = int(run_git("show", "-s", "--format=%ct", "HEAD"))
    try:
        repository = run_git("remote", "get-url", "origin")
    except subprocess.CalledProcessError:
        repository = "unknown"
    version_match = re.search(r"^version:\s*([^\s]+)\s*$", (PLUGIN / "plugin.yaml").read_text(), re.MULTILINE)
    if not version_match:
        raise SystemExit("Hermes plugin version is missing.")
    version = version_match.group(1)
    archive_name = f"remanager-hermes-agentic-{version}.tar.gz"

    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="reman-hermes-candidate-") as temporary:
        stage = Path(temporary) / "reman-agentic"
        stage.mkdir()
        for relative in SOURCE_FILES:
            source = PLUGIN / relative
            validate_source(source)
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)

        dependencies = {
            "schemaVersion": 1,
            "component": "reman-agentic",
            "version": version,
            "runtime": {"name": "Python", "minimumVersion": "3.10"},
            "thirdPartyRuntimeDependencies": [],
            "stdlibModules": ["http.client", "json", "os", "pathlib", "re", "socket", "urllib"],
        }
        provenance = {
            "schemaVersion": 1,
            "builder": "integrations/scripts/build-hermes-candidate.py",
            "format": "Hermes directory plugin",
            "plugin": {"name": "reman-agentic", "version": version},
            "source": {"repository": repository, "commit": commit, "tree": tree},
            "sourceDateEpoch": source_epoch,
            "dirtySourceAllowed": bool(allow_dirty),
        }
        (stage / "DEPENDENCIES.json").write_bytes(canonical_json(dependencies))
        (stage / "PROVENANCE.json").write_bytes(canonical_json(provenance))
        payload = [file_entry(stage, path) for path in sorted(stage.rglob("*")) if path.is_file()]
        embedded_manifest = {
            "schemaVersion": 1,
            "archive": archive_name,
            "plugin": {"name": "reman-agentic", "version": version},
            "payloadFiles": payload,
        }
        (stage / "RELEASE-MANIFEST.json").write_bytes(canonical_json(embedded_manifest))

        complete_manifest = {
            "schemaVersion": 1,
            "archive": archive_name,
            "plugin": {"name": "reman-agentic", "version": version},
            "files": [file_entry(stage, path) for path in sorted(stage.rglob("*")) if path.is_file()],
        }
        archive_path = output / archive_name
        with archive_path.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=source_epoch) as compressed:
                with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                    for path in sorted(stage.rglob("*")):
                        if not path.is_file():
                            continue
                        relative = path.relative_to(stage).as_posix()
                        add_tar_entry(
                            archive,
                            "reman-agentic/" + relative,
                            path.read_bytes(),
                            0o755 if path.suffix == ".sh" else 0o644,
                            source_epoch,
                        )

        archive_digest = digest(archive_path)
        base_name = f"remanager-hermes-agentic-{version}"
        (output / f"{base_name}.sha256").write_text(f"{archive_digest}  {archive_name}\n", encoding="ascii")
        (output / f"{base_name}.manifest.json").write_bytes(canonical_json(complete_manifest))
        (output / f"{base_name}.provenance.json").write_bytes(canonical_json(provenance))
        (output / f"{base_name}.dependencies.json").write_bytes(canonical_json(dependencies))

    print(json.dumps({
        "archive": str(archive_path),
        "sha256": archive_digest,
        "version": version,
        "commit": commit,
        "tree": tree,
        "files": len(complete_manifest["files"]),
    }, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    build(args.output.resolve(), args.allow_dirty)


if __name__ == "__main__":
    main()
