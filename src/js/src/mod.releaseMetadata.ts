import { createHash } from "node:crypto";
import { downloadRelease, maxArchive, maxMetadata } from "./mod.downloadRelease";
import { releaseAssetUrl } from "./mod.releaseAssetUrl";
import { updateError } from "./mod.updateError";
import type { PublishedRelease, ReleasePlan } from "./types";

const commitPattern = /^[0-9a-f]{40}$/;
const hashPattern = /^[0-9a-f]{64}$/;

// SHA256SUMS and a checksum-verified release.json that names this archive.
export async function releaseMetadata(release: PublishedRelease, archive: string, signal: AbortSignal): Promise<{ plan: ReleasePlan; sums: Map<string, string> }> {
  const diagnose = `curl -fsSL ${releaseAssetUrl(release.tag, "release.json")}`;
  for (const name of [archive, "release.json", "SHA256SUMS"]) {
    const matches = release.assets.filter(asset => asset.name === name);
    for (const asset of matches) {
      if (asset.size <= 0 || asset.size > maxArchive || (name !== archive && asset.size > maxMetadata)) throw updateError(`invalid asset size: ${name}`, diagnose);
    }
    if (matches.length !== 1) throw updateError(`release missing or duplicates asset: ${name}`, diagnose);
  }
  const listing = new TextDecoder().decode(await downloadRelease(releaseAssetUrl(release.tag, "SHA256SUMS"), maxMetadata, signal));
  const sums = new Map<string, string>();
  for (const line of listing.trim().split("\n")) {
    const parts = line.split("  ");
    if (parts.length !== 2 || !hashPattern.test(parts[0]) || parts[1] === "" || sums.has(parts[1])) throw updateError("invalid SHA256SUMS", diagnose);
    sums.set(parts[1], parts[0]);
  }
  if (!sums.get(archive) || !sums.get("release.json")) throw updateError("missing release checksum", diagnose);
  const data = await downloadRelease(releaseAssetUrl(release.tag, "release.json"), maxMetadata, signal);
  if (createHash("sha256").update(data).digest("hex") !== sums.get("release.json")) throw updateError("release.json checksum mismatch", diagnose);
  let plan: ReleasePlan;
  try { plan = JSON.parse(new TextDecoder().decode(data)); }
  catch (error) { throw updateError(`invalid release.json: ${(error as Error).message}`, diagnose); }
  if (!plan || typeof plan !== "object" || plan.schema !== "maw.release.v1" || plan.skip !== false || plan.tag !== release.tag || typeof plan.commit !== "string" || !commitPattern.test(plan.commit)) {
    throw updateError("release metadata mismatch", diagnose);
  }
  if (!Array.isArray(plan.archives) || !plan.archives.includes(archive)) throw updateError("archive absent from release metadata", diagnose);
  return { plan, sums };
}
