# scripts/fixtures/

Cross-language golden fixtures. Fermix core (Elixir) and `pluginlib.py` (this
repo) must produce identical bytes for both algorithms below — a plugin whose
`descriptor_sha256` or tree digest differs between the two sides is refused at
install even though it passed publish. These files are the contract; changing a
value here is a wire change and must land on both sides in the same release.

Every fixture file is pure ASCII, so the bytes are unambiguous in a diff.

## `jcs/` — RFC 8785 JSON Canonicalization Scheme

```json
{
  "name": "…",
  "description": "…",
  "input_json": "<raw JSON TEXT — parse this, do not re-serialize it first>",
  "expected": "<canonical JSON text>",
  "expected_sha256": "<sha256 of expected, UTF-8>"
}
```

A refusal fixture carries `"error"` instead of `"expected"`: parsing
`input_json` must fail before canonicalization.

Consume it as: parse `input_json` **rejecting duplicate object keys**,
canonicalize, compare to `expected` byte for byte, and confirm SHA-256 of those
bytes equals `expected_sha256`.

Covered: Unicode (astral plane, and the UTF-16 surrogate ordering that puts
U+1F600 *before* U+E000), escaping (`\"`, `\\`, U+0000–U+001F, and DEL emitted
literally), integers vs floats (`1`, `1.0`, `1e21`, `-0`, the 1e21/1e-7
ECMAScript exponent thresholds), array order preserved, object key order
normalized, explicit `null`, and duplicate-key refusal.

`descriptor.json` also carries `descriptor_parts`, the
`{name, parameters, output_schema, upstream_annotations}` of a manifest tool:
`expected_sha256` is exactly what that tool must declare as `descriptor_sha256`
(M27 §7.6).

## `tree_digest/` — `tree_digest_v2` (M27 §9.3)

```json
{
  "name": "…",
  "files": [{"path": "a/b", "content_b64": "…"}],
  "expected_sha256": "…"
}
```

SHA-256 over `b"fermix-plugin-tree-v2\0"`, a big-endian u32 file count, then per
file in bytewise-sorted NFC-normalized UTF-8 relative-path order:
`u32 path_length || path_bytes || u64 content_length || content_bytes`.
Directories and filesystem metadata are excluded; links are refused.

Covered: prefix-like path ordering (`a` < `a.b` < `a/b` < `ab`), empty files,
Unicode paths, NFC/NFD path equivalence, and path/content length boundaries.

`"filesystem_realizable": false` marks a fixture that cannot be written to a
real filesystem (a file and a directory of the same name); it still pins the
digest domain. `"equals_fixture"` marks a fixture whose digest must equal
another's.
