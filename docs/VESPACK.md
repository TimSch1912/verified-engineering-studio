# VES Evidence Package v1

A directory-form `.vespack` is the read-only boundary between an engineering source workflow and
Verified Engineering Studio. The package contains evidence, not executable solver or simulator
logic.

## Layout

```text
example.vespack/
├── manifest.json
├── evidence.json
├── provenance.json
├── source-hashes.sha256
├── timeseries/        # optional, declared files only
├── artifacts/         # optional, declared files only
└── reports/           # optional, declared files only
```

`manifest.json` identifies the package, project, case, immutable run, module, adapter and
publication scope. Every payload file has a role, media type, exact byte count and SHA-256. The
ASCII hash index independently repeats the payload digests.

`evidence.json` uses `ves.evidence.v1`: metrics, artifacts, claims, limitations, public provenance
and method references. `provenance.json` records the producer and source-run identity. Its public
display fields must exactly match the evidence document.

## Validation boundary

`ves pack validate <path>` rejects a package when any of these conditions is found:

- schema, module, case, run or provenance disagreement;
- missing, duplicate, undeclared or hash/size-mismatched files;
- absolute/traversal paths, symbolic links, special files or executable payloads;
- configured file-count, individual-size or total-size limit violations;
- duplicate evidence IDs or insecure artifact/reference URL schemes;
- missing publication-rights metadata for a public artifact;
- API-key-shaped values, private-key headers or absolute home-directory paths in text payloads.

The validator performs no network access and executes no package content. The public Laurons v9
case is loaded only after this gate succeeds.

## Reproducible identity

After all payload hashes validate, VES canonicalizes the typed manifest and calculates a package
SHA-256. Identical manifests and payload identities reproduce the same fingerprint. Changing raw
evidence produces a new package identity; a later AI review is a derived record and never rewrites
the source package.

## CLI examples

```bash
ves pack validate src/ves/modules/cfd/packages/laurons-v9.vespack
ves pack validate src/ves/modules/cfd/packages/laurons-v9.vespack --json
```

The command exits with `0` for a valid package and `2` for an invalid package, making the same gate
usable in local workflows and CI.
