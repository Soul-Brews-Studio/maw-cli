# MCP trace/context index workload — issue #6

`maw index FILE` (or `maw index -` for stdin) parses MCP-shaped JSONL and builds
an in-memory inverted index. This is a real local processing command, not a live
server throughput claim. Implementations share this input/output contract.

## Records

Each nonempty line is one UTF-8 JSON object:

```json
{"jsonrpc":"2.0","id":1,"result":{"structuredContent":{"file":"src/example.go","symbol":"Example","text":"func Example() { return value }"}}}
```

The JSON-RPC version must be `2.0`; `result.structuredContent.file`, `symbol`,
and `text` must be strings. File/symbol are nonempty and must not contain NUL.
Extra fields are allowed. Normalized records use unique object member names and
finite representable numbers; duplicate keys and extreme numeric overflow are
outside this comparison domain (parser-specific rejection/overwrite behavior).
Normalized input nesting is at most 32 arrays/objects deep; deeper arbitrary
JSON is outside the benchmark domain because parser recursion limits differ. This is a documented normalized context result schema,
not an assumption that every Serena/CodeGraph tool emits these fields natively.
JSON framing whitespace-only lines (space/tab/CR/LF) are ignored; final newline optional. Malformed JSON,
invalid UTF-8, unpaired UTF-16 surrogate escapes, absent/wrong fields, and input over 64 MiB fail with nonzero exit
and no success summary. Usage errors return 2. No partial success on bad records.

## Index algorithm

- Input byte count includes framing/whitespace; text byte count is decoded UTF-8.
- Tokenize text on anything outside ASCII `[A-Za-z0-9_]`; lowercase ASCII letters.
- Build `term -> [zero-based record IDs]` postings, deduplicating a term within
  each record. Keep the actual postings lists, not merely estimated counters.
- Unique symbol keys are `(file, symbol)` pairs (NUL-separated encoding is safe
  because metadata cannot contain NUL). No Unicode normalization is performed.
- Sort terms lexically; for each term hash UTF-8 `term:document_frequency\n`
  using FNV-1a 64-bit (offset14695981039346656037, prime1099511628211, modulo2^64).
  This checksum verifies outputs; it is not a cryptographic/security digest.

## Output

Exactly one JSON object, fields may appear in any order:

```json
{"records":1,"input_bytes":150,"text_bytes":37,"unique_symbols":1,"unique_terms":5,"postings":5,"checksum":"0123456789abcdef"}
```

The numbers/hash above illustrate shape only. All counters are actual measured
integers, checksum is exactly 16 lowercase hex digits. An independent Python
fixture oracle will compute expected results and smoke-check every implementation.

The benchmark will label its generated corpus and size, validate outputs before
timing, and record per-process wall/user/system time plus peak RSS. Full-input
buffering is allowed for this bounded prototype and must be disclosed; no hidden
external parsers or runtime subprocesses inside the indexing implementations.
