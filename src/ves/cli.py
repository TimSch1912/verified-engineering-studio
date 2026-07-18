from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from ves.core.package import PackageValidationError, validate_evidence_package
from ves.modules.cfd.convergence import analyze_three_grid_sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ves",
        description="Validate and inspect Verified Engineering Studio evidence packages.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    pack = commands.add_parser("pack", help="Evidence package operations")
    pack_commands = pack.add_subparsers(dest="pack_command", required=True)
    validate = pack_commands.add_parser(
        "validate",
        help="Validate structure, schemas, hashes, publication metadata and privacy boundaries.",
    )
    validate.add_argument("package", help="Path to a directory-form .vespack")
    validate.add_argument("--json", action="store_true", help="Emit a machine-readable result")

    cfd = commands.add_parser("cfd", help="CFD evidence calculations")
    cfd_commands = cfd.add_subparsers(dest="cfd_command", required=True)
    convergence = cfd_commands.add_parser(
        "convergence",
        help="Evaluate a constant-ratio three-grid sequence without hiding invalid regimes.",
    )
    for level in ("fine", "medium", "coarse"):
        convergence.add_argument(f"--{level}-value", required=True, type=float)
        convergence.add_argument(f"--{level}-cells", required=True, type=int)
    convergence.add_argument("--dimensions", type=int, default=3)
    convergence.add_argument("--json", action="store_true", help="Emit a machine-readable result")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "pack" and args.pack_command == "validate":
        return _validate_package(args.package, json_output=args.json)
    if args.command == "cfd" and args.cfd_command == "convergence":
        return _cfd_convergence(args)
    raise AssertionError("unreachable command")


def _validate_package(path: str, *, json_output: bool) -> int:
    try:
        package = validate_evidence_package(path)
    except PackageValidationError as exc:
        if json_output:
            print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"INVALID: {exc}")
        return 2

    payload = {
        "valid": True,
        "schema_version": package.manifest.schema_version,
        "package_id": package.manifest.package_id,
        "module_id": package.manifest.module_id,
        "case_id": package.manifest.case_id,
        "run_id": package.manifest.run_id,
        "publication_scope": package.manifest.publication_scope,
        "files": len(package.manifest.files),
        "total_bytes": package.total_bytes,
        "package_sha256": package.package_sha256,
    }
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(
            "VALID "
            f"{payload['package_id']} · {payload['module_id']}/{payload['case_id']} · "
            f"{payload['files']} files · sha256 {payload['package_sha256']}"
        )
    return 0


def _cfd_convergence(args: argparse.Namespace) -> int:
    try:
        result = analyze_three_grid_sequence(
            fine_value=args.fine_value,
            medium_value=args.medium_value,
            coarse_value=args.coarse_value,
            fine_cells=args.fine_cells,
            medium_cells=args.medium_cells,
            coarse_cells=args.coarse_cells,
            dimensions=args.dimensions,
        )
    except ValueError as exc:
        if args.json:
            print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"INVALID: {exc}")
        return 2

    payload = result.as_dict()
    payload["valid"] = result.classification == "monotonic_convergence"
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result.classification}: {result.note}")
        if result.gci21_percent is not None:
            print(
                f"p={result.observed_order:.6g} · extrapolated={result.extrapolated_value:.6g} "
                f"· GCI21={result.gci21_percent:.6g}%"
            )
    return 0 if payload["valid"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
