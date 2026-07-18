import hashlib
import json
import shutil
from pathlib import Path

import pytest

from ves.cli import main
from ves.core.package import PackageValidationError, validate_evidence_package

PACKAGE = (
    Path(__file__).parents[1]
    / "src"
    / "ves"
    / "modules"
    / "cfd"
    / "packages"
    / "laurons-v9.vespack"
)


def _copy_package(tmp_path: Path) -> Path:
    target = tmp_path / "case.vespack"
    shutil.copytree(PACKAGE, target)
    return target


def _rehash(root: Path, relative: str) -> None:
    payload = (root / relative).read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["files"]:
        if item["path"] == relative:
            item["sha256"] = digest
            item["size_bytes"] = len(payload)
            break
    else:
        raise AssertionError(f"missing manifest entry for {relative}")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    hash_path = root / "source-hashes.sha256"
    hashes = {}
    for line in hash_path.read_text(encoding="ascii").splitlines():
        old_digest, path = line.split("  ", 1)
        hashes[path] = digest if path == relative else old_digest
    hash_path.write_text(
        "".join(f"{hashes[path]}  {path}\n" for path in sorted(hashes)),
        encoding="ascii",
    )


def test_curated_cfd_package_is_valid_and_reproducible():
    first = validate_evidence_package(PACKAGE)
    second = validate_evidence_package(PACKAGE)

    assert first.manifest.package_id == "ves.laurons-ii.v9.public"
    assert first.evidence.case_id == "laurons-v9"
    assert first.provenance.display == first.evidence.provenance
    assert first.package_sha256 == second.package_sha256
    assert len(first.manifest.files) == 5
    assert first.total_bytes == 5_019_244
    assert all(
        artifact.package_path and artifact.sha256
        for artifact in first.evidence.artifacts
        if artifact.kind in {"image", "video"}
    )
    assert {reference.id for reference in first.evidence.references} == {
        "ref.ittc2017.vv",
        "ref.versteeg2007.ch10",
    }


def test_tampered_payload_and_undeclared_file_fail_closed(tmp_path):
    tampered = _copy_package(tmp_path)
    evidence = tampered / "evidence.json"
    evidence.write_text(evidence.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(PackageValidationError, match="size does not match|sha256 mismatch"):
        validate_evidence_package(tampered)

    clean = _copy_package(tmp_path / "second")
    (clean / "notes.txt").write_text("undeclared", encoding="utf-8")
    with pytest.raises(PackageValidationError, match="undeclared files"):
        validate_evidence_package(clean)

    media = _copy_package(tmp_path / "third")
    video_path = media / "artifacts" / "mesh-flythrough.mp4"
    video = bytearray(video_path.read_bytes())
    video[-1] ^= 1
    video_path.write_bytes(video)
    with pytest.raises(PackageValidationError, match="sha256 mismatch"):
        validate_evidence_package(media)


@pytest.mark.parametrize(
    "forbidden",
    [
        "sk-proj-this-is-a-fake-but-secret-shaped-value-1234567890",
        "/home/timo/private/source-case",
        "C:\\Users\\timo\\private\\source-case",
    ],
)
def test_secret_shaped_values_and_private_paths_are_rejected(tmp_path, forbidden):
    package = _copy_package(tmp_path)
    evidence_path = package / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["claims"].append(forbidden)
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    _rehash(package, "evidence.json")

    with pytest.raises(PackageValidationError, match="secret|private path"):
        validate_evidence_package(package)


def test_cli_reports_valid_and_invalid_packages(tmp_path, capsys):
    assert main(["pack", "validate", str(PACKAGE), "--json"]) == 0
    valid = json.loads(capsys.readouterr().out)
    assert valid["valid"] is True
    assert len(valid["package_sha256"]) == 64

    package = _copy_package(tmp_path)
    (package / "source-hashes.sha256").write_text("broken\n", encoding="ascii")
    assert main(["pack", "validate", str(package), "--json"]) == 2
    invalid = json.loads(capsys.readouterr().out)
    assert invalid["valid"] is False
