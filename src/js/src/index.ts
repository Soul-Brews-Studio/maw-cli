import { createReadStream } from "node:fs";

const maxInputBytes = 64 * 1024 * 1024;

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

// JSON.parse permits lone UTF-16 surrogates; other parsers reject them.
function validUnicode(value: unknown): boolean {
  const pending: unknown[] = [value];
  while (pending.length) {
    const item = pending.pop();
    if (typeof item === "string") {
      for (let i = 0; i < item.length; i++) {
        const code = item.charCodeAt(i);
        if (code >= 0xdc00 && code <= 0xdfff) return false;
        if (code >= 0xd800 && code <= 0xdbff) {
          const low = item.charCodeAt(++i);
          if (!(low >= 0xdc00 && low <= 0xdfff)) return false;
        }
      }
    } else if (Array.isArray(item)) {
      for (const child of item) pending.push(child);
    } else if (object(item)) {
      for (const [key, child] of Object.entries(item)) pending.push(key, child);
    }
  }
  return true;
}

// This bounded prototype buffers the input before building the in-memory index.
export async function indexTrace(args: string[]): Promise<number> {
  if (args.length !== 1) {
    console.error("maw: usage: maw index FILE|-");
    return 2;
  }
  try {
    const chunks: Buffer[] = [];
    let inputBytes = 0;
    const input = args[0] === "-" ? process.stdin : createReadStream(args[0]);
    for await (const chunk of input) {
      const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      inputBytes += bytes.length;
      if (inputBytes > maxInputBytes) throw new Error("input exceeds 64 MiB");
      chunks.push(bytes);
    }
    const source = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true })
      .decode(Buffer.concat(chunks, inputBytes));
    const terms = new Map<string, number[]>();
    const symbols = new Set<string>();
    let records = 0;
    let textBytes = 0;
    let postings = 0;
    for (const [lineIndex, line] of source.split("\n").entries()) {
      if (/^[ \t\r]*$/.test(line)) continue;
      let record: unknown;
      try {
        record = JSON.parse(line);
        if (!validUnicode(record)) throw new Error("invalid Unicode");
      } catch {
        throw new Error(`line ${lineIndex + 1}: invalid JSON`);
      }
      if (!object(record) || record.jsonrpc !== "2.0" || !object(record.result)
        || !object(record.result.structuredContent)) {
        throw new Error(`line ${lineIndex + 1}: invalid context result`);
      }
      const { file, symbol, text } = record.result.structuredContent;
      if (typeof file !== "string" || !file || file.includes("\0")
        || typeof symbol !== "string" || !symbol || symbol.includes("\0")
        || typeof text !== "string") {
        throw new Error(`line ${lineIndex + 1}: invalid file, symbol, or text`);
      }
      symbols.add(`${file}\0${symbol}`);
      textBytes += Buffer.byteLength(text, "utf8");
      const documentTerms = new Set(text.match(/[A-Za-z0-9_]+/g)?.map(term => term.toLowerCase()));
      for (const term of documentTerms) {
        let documents = terms.get(term);
        if (!documents) {
          documents = [];
          terms.set(term, documents);
        }
        documents.push(records);
        postings++;
      }
      records++;
    }
    let checksum = 14695981039346656037n;
    for (const term of [...terms.keys()].sort()) {
      for (const byte of Buffer.from(`${term}:${terms.get(term)!.length}\n`)) {
        checksum = BigInt.asUintN(64, (checksum ^ BigInt(byte)) * 1099511628211n);
      }
    }
    console.log(JSON.stringify({
      records,
      input_bytes: inputBytes,
      text_bytes: textBytes,
      unique_symbols: symbols.size,
      unique_terms: terms.size,
      postings,
      checksum: checksum.toString(16).padStart(16, "0"),
    }));
    return 0;
  } catch (error) {
    console.error(`maw: index: ${error instanceof Error ? error.message : error}`);
    return 1;
  }
}
