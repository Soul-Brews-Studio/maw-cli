import { closeSync, lstatSync, mkdirSync, mkdtempSync, openSync, realpathSync, renameSync, rmdirSync, rmSync, writeSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { downloadRelease, maxArchive } from "./mod.downloadRelease";
import { releaseAssetUrl } from "./mod.releaseAssetUrl";
import { unpackRelease } from "./mod.unpackRelease";
import { proveCandidate } from "./mod.proveCandidate";
import { updateError } from "./mod.updateError";
import { shellQuote } from "./mod.shellQuote";
import type { PublishedRelease, ReleasePlan, ReleasePlatform } from "./types";

// Download, verify, unpack and prove a candidate in a private sibling staging
// directory, then replace the running executable with one same-filesystem
// rename. Any failure before the rename leaves the original file in place.
export async function installRelease(release: PublishedRelease, plan: ReleasePlan, sum: string, asset: string, platform: ReleasePlatform, signal: AbortSignal): Promise<string> {
  const target = realpathSync(process.execPath);
  const directory = dirname(target);
  const inspect = `ls -ld ${shellQuote(directory)}`;
  const original = lstatSync(target, { bigint: true });
  if (!original.isFile() || (original.mode & 0o6000n) !== 0n) throw updateError("refusing non-regular or privileged executable", `ls -l ${shellQuote(target)}`);
  const lock = `${target}.update-lock`;
  try { mkdirSync(lock, 0o700); }
  catch (error) {
    const stale = (error as NodeJS.ErrnoException).code === "EEXIST";
    throw updateError(`cannot lock ${target} (another update, stale lock, or directory not writable): ${(error as Error).message}`,
      stale ? `rmdir ${shellQuote(lock)}  # only after confirming no maw update is still running` : inspect);
  }
  let stage = "";
  try {
    try { stage = mkdtempSync(join(directory, ".maw-js-update-")); }
    catch (error) { throw updateError(`cannot stage beside ${target}: ${(error as Error).message}`, inspect); }
    const archive = join(stage, "archive.tar.gz");
    const hash = createHash("sha256");
    const file = openSync(archive, "wx", 0o600);
    try {
      await downloadRelease(releaseAssetUrl(release.tag, asset), maxArchive, signal, chunk => {
        try { for (let offset = 0; offset < chunk.length; ) offset += writeSync(file, chunk, offset); }
        catch (error) { throw updateError(`cannot write ${archive}: ${(error as Error).message}; original executable unchanged`, `df -h ${shellQuote(directory)}`); }
        hash.update(chunk);
      });
    } finally { closeSync(file); }
    if (hash.digest("hex") !== sum) throw updateError("archive checksum mismatch; original executable unchanged");
    const candidate = join(stage, "maw-js");
    await unpackRelease(archive, candidate, plan, platform);
    proveCandidate(candidate, plan.tag);
    const now = lstatSync(target, { bigint: true });
    if (original.dev !== now.dev || original.ino !== now.ino || original.size !== now.size || original.mtimeNs !== now.mtimeNs) {
      throw updateError("installed executable changed during update; refusing replacement", `${shellQuote(target)} version`);
    }
    signal.throwIfAborted();
    // Candidate is proven first; one same-filesystem rename replaces the old name without a gap.
    renameSync(candidate, target);
    return target;
  } finally {
    if (stage) rmSync(stage, { recursive: true, force: true });
    try { rmdirSync(lock); } catch { /* already gone */ }
  }
}
