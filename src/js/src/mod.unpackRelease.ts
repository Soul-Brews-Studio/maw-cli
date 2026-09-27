import { chmodSync, closeSync, createReadStream, fsyncSync, openSync, writeSync } from "node:fs";
import { createHash } from "node:crypto";
import { createGunzip } from "node:zlib";
import { pipeline } from "node:stream/promises";
import { maxBinary } from "./mod.downloadRelease";
import { validExecutableHeader } from "./mod.validExecutableHeader";
import { updateError } from "./mod.updateError";
import type { ReleasePlan, ReleasePlatform } from "./types";

const block = 512;
const limit = maxBinary + 1024 * 1024;

// A hand-written reader for exactly two regular USTAR members, maw-js and
// RELEASE.json. Links, directories, paths, PAX/GNU headers, duplicates and any
// other member are refused, as are non-zero bytes after the end of the archive.
// The decompressed stream is bounded and the gzip CRC is checked on the way out.
export async function unpackRelease(archive: string, candidate: string, plan: ReleasePlan, platform: ReleasePlatform): Promise<void> {
  const seen = new Set<string>();
  let metadata: Record<string, unknown> = {};
  let binaryDigest = "";
  try {
    await pipeline(createReadStream(archive), createGunzip(), async (source: AsyncIterable<Buffer>) => {
      const reader = new Reader(source[Symbol.asyncIterator]());
      for (;;) {
        const header = await reader.read(block);
        if (header.length === 0) break;
        if (header.length !== block) throw updateError("unexpected end of archive");
        if (header.every(byte => byte === 0)) {
          const second = await reader.read(block);
          if (second.length === 0 || (second.length === block && second.every(byte => byte === 0))) break;
          throw updateError("invalid archive header");
        }
        const member = parseHeader(header);
        if ((member.name !== "maw-js" && member.name !== "RELEASE.json") || seen.has(member.name) || !member.ustar || (member.type !== "0" && member.type !== "\0")) {
          throw updateError("unsafe or unexpected archive member");
        }
        seen.add(member.name);
        if (member.name === "RELEASE.json") {
          if (member.size > 16384) throw updateError("archive metadata too large");
          const data = await reader.exact(member.size);
          let parsed: unknown;
          try { parsed = JSON.parse(data.toString("utf8")); }
          catch (error) { throw updateError(`invalid archive metadata: ${(error as Error).message}`); }
          metadata = parsed && typeof parsed === "object" ? parsed as Record<string, unknown> : {};
        } else {
          if (member.size < 32 || member.size > maxBinary || member.mode !== 0o755) throw updateError("invalid executable size or permissions");
          const head = await reader.exact(32);
          if (!validExecutableHeader(head, platform)) throw updateError("binary format/architecture mismatch");
          const digest = createHash("sha256");
          const file = openSync(candidate, "wx", 0o600);
          try {
            for (let piece: Buffer = head, remaining = member.size; ; ) {
              for (let offset = 0; offset < piece.length; ) offset += writeSync(file, piece, offset);
              digest.update(piece);
              remaining -= piece.length;
              if (remaining === 0) break;
              piece = await reader.next(Math.min(remaining, 1 << 20));
              if (piece.length === 0) throw updateError("unexpected end of archive");
            }
            fsyncSync(file);
          } finally { closeSync(file); }
          binaryDigest = digest.digest("hex");
        }
        await reader.exact((block - (member.size % block)) % block);
      }
      // tar EOF can precede the gzip footer. Drain to validate CRC and reject trailing payloads.
      for (let rest = await reader.next(65536); rest.length; rest = await reader.next(65536)) {
        if (rest.some(byte => byte !== 0)) throw updateError("unexpected trailing archive data");
      }
    });
  } catch (error) {
    const code = String((error as NodeJS.ErrnoException).code ?? "");
    if (code.startsWith("Z_")) throw updateError(`archive decompression failed: ${(error as Error).message}`);
    throw error;
  }
  if (seen.size !== 2 || metadata.tag !== plan.tag || metadata.commit !== plan.commit || metadata.language !== "js" || metadata.os !== platform.os || metadata.arch !== platform.arch || metadata.sha256 !== binaryDigest || !binaryDigest) {
    throw updateError("archive metadata/binary checksum mismatch");
  }
  chmodSync(candidate, 0o755);
}

// Pulls decompressed bytes on demand and refuses to go past the size bound.
class Reader {
  private pending = Buffer.alloc(0);
  private total = 0;
  constructor(private source: AsyncIterator<Buffer>) {}

  // At least one byte and at most `max`; empty only at end of stream.
  async next(max: number): Promise<Buffer> {
    if (this.pending.length === 0) {
      const chunk = await this.source.next();
      if (chunk.done) return Buffer.alloc(0);
      this.total += chunk.value.length;
      if (this.total >= limit) throw updateError("decompressed archive exceeds size limit");
      this.pending = chunk.value;
    }
    const piece = this.pending.subarray(0, max);
    this.pending = this.pending.subarray(piece.length);
    return piece;
  }

  // Exactly `size` bytes, or fewer only at end of stream.
  async read(size: number): Promise<Buffer> {
    const pieces: Buffer[] = [];
    for (let have = 0; have < size; ) {
      const piece = await this.next(size - have);
      if (piece.length === 0) break;
      pieces.push(piece);
      have += piece.length;
    }
    return Buffer.concat(pieces);
  }

  async exact(size: number): Promise<Buffer> {
    const data = await this.read(size);
    if (data.length !== size) throw updateError("unexpected end of archive");
    return data;
  }
}

// Go's archive/tar rules: a valid checksum (unsigned or signed), USTAR magic
// without the STAR trailer, octal numbers padded with spaces or NULs, and the
// prefix field joined to the name.
function parseHeader(header: Buffer): { name: string; mode: number; size: number; type: string; ustar: boolean } {
  let unsigned = 0, signed = 0;
  for (let n = 0; n < block; n++) {
    const byte = n >= 148 && n < 156 ? 0x20 : header[n];
    unsigned += byte;
    signed += byte > 127 ? byte - 256 : byte;
  }
  const checksum = octal(header, 148, 8);
  if (checksum !== unsigned && checksum !== signed) throw updateError("invalid archive header");
  const ustar = header.toString("latin1", 257, 263) === "ustar\0" && header.toString("latin1", 508, 512) !== "tar\0";
  const name = text(header, 0, 100);
  const prefix = ustar ? text(header, 345, 155) : "";
  return { name: prefix ? `${prefix}/${name}` : name, mode: octal(header, 100, 8), size: octal(header, 124, 12), type: header.toString("latin1", 156, 157), ustar };
}

function text(header: Buffer, start: number, length: number): string {
  const field = header.subarray(start, start + length);
  const end = field.indexOf(0);
  return field.toString("latin1", 0, end < 0 ? length : end);
}

function octal(header: Buffer, start: number, length: number): number {
  const field = header.toString("latin1", start, start + length).replace(/^[ \0]+|[ \0]+$/g, "");
  if (field === "") return 0;
  if (!/^[0-7]+$/.test(field)) throw updateError("invalid archive header");
  return parseInt(field, 8);
}
