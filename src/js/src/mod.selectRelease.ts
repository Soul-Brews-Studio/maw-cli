import { apiOrigin, repository } from "./mod.validReleaseUrl";
import { downloadRelease, maxMetadata } from "./mod.downloadRelease";
import { compareTags, tagPattern } from "./mod.compareTags";
import { updateError } from "./mod.updateError";
import { shellQuote } from "./mod.shellQuote";
import type { PublishedRelease } from "./types";

// The numerically newest published alpha among the newest 30 releases, or the
// exact tag asked for. Drafts and non-CalVer tags never qualify.
export async function selectRelease(tag: string, signal: AbortSignal): Promise<PublishedRelease> {
  const endpoint = `${apiOrigin}/repos/${repository}/releases${tag ? `/tags/${tag}` : "?per_page=30"}`;
  const diagnose = `curl -sS ${shellQuote(endpoint)}`;
  let data: unknown;
  try { data = JSON.parse(new TextDecoder().decode(await downloadRelease(endpoint, maxMetadata, signal))); }
  catch (error) { throw (error as { fix?: string[] }).fix ? error : updateError(`invalid release JSON: ${(error as Error).message}`, diagnose); }
  let releases: PublishedRelease[];
  if (tag) {
    const release = published(data, diagnose);
    if (release.tag !== tag) throw updateError("release tag mismatch", diagnose);
    releases = [release];
  } else {
    if (!Array.isArray(data)) throw updateError("invalid release JSON: expected a release list", diagnose);
    releases = data.map(value => published(value, diagnose));
  }
  let best: PublishedRelease | undefined;
  for (const release of releases) {
    if (release.draft || !release.published || !tagPattern.test(release.tag)) continue;
    if (!best || compareTags(release.tag, best.tag) > 0) best = release;
  }
  if (!best) throw updateError("no published alpha release found in the newest 30 releases", diagnose);
  return best;
}

// Mirror Go's json.Unmarshal: absent fields are empty, mistyped fields fail.
function published(value: unknown, diagnose: string): PublishedRelease {
  const invalid = () => updateError("invalid release JSON", diagnose);
  if (!value || typeof value !== "object" || Array.isArray(value)) throw invalid();
  const { tag_name: tag = "", draft = false, published_at: published = "", assets = [] } = value as Record<string, unknown>;
  if (typeof tag !== "string" || typeof draft !== "boolean" || (published !== null && typeof published !== "string") || (assets !== null && !Array.isArray(assets))) throw invalid();
  return {
    tag, draft, published: published ?? "",
    assets: (assets ?? []).map((asset: unknown) => {
      if (!asset || typeof asset !== "object") throw invalid();
      const { name = "", size = 0 } = asset as Record<string, unknown>;
      if (typeof name !== "string" || typeof size !== "number") throw invalid();
      return { name, size };
    }),
  };
}
