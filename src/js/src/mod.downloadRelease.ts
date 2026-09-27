import { validReleaseUrl } from "./mod.validReleaseUrl";
import { updateError } from "./mod.updateError";
import { shellQuote } from "./mod.shellQuote";

export const maxMetadata = 2 * 1024 * 1024;
export const maxBinary = 512 * 1024 * 1024;
export const maxArchive = maxBinary + 1024 * 1024;
const redirects = new Set([301, 302, 303, 307, 308]);

// One bounded GitHub download. Streams to `write` when given, otherwise
// returns the bytes. Every hop, redirects included, must pass the allowlist.
export async function downloadRelease(raw: string, limit: number, signal: AbortSignal, write?: (chunk: Uint8Array) => void): Promise<Uint8Array> {
  const diagnose = `curl -sSIL ${shellQuote(raw)}`;
  try { return await fetchBounded(raw, limit, signal, diagnose, write); }
  catch (error) {
    // Network, TLS and abort failures get the same diagnostic as HTTP errors.
    if ((error as { fix?: string[] }).fix) throw error;
    throw updateError((error as Error).message || String(error), diagnose);
  }
}

async function fetchBounded(raw: string, limit: number, signal: AbortSignal, diagnose: string, write?: (chunk: Uint8Array) => void): Promise<Uint8Array> {
  if (!validReleaseUrl(raw)) throw updateError("refusing non-GitHub HTTPS download", diagnose);
  const deadline = AbortSignal.any([signal, AbortSignal.timeout(90_000)]);
  const headers = { "User-Agent": "maw-js-update", Accept: "application/vnd.github+json, application/octet-stream" };
  let url = raw;
  let response: Response;
  for (let hop = 0; ; hop++) {
    response = await fetch(url, { redirect: "manual", signal: deadline, headers });
    const location = response.headers.get("location");
    if (!redirects.has(response.status) || !location) break;
    await response.body?.cancel();
    let next = "";
    try { next = new URL(location, url).href; } catch { /* refused below */ }
    // Go's client refuses the redirect once five requests have been made.
    if (hop >= 4 || !validReleaseUrl(next)) throw updateError("refusing download redirect", diagnose);
    url = next;
  }
  if (response.status !== 200) {
    await response.body?.cancel();
    throw updateError(`GitHub returned HTTP ${response.status} (release may be unavailable or rate limited)`, diagnose);
  }
  if (Number(response.headers.get("content-length") ?? 0) > limit) {
    await response.body?.cancel();
    throw updateError("download exceeds size limit", diagnose);
  }
  const chunks: Uint8Array[] = [];
  let total = 0;
  if (response.body) {
    for await (const chunk of response.body) {
      total += chunk.length;
      if (total > limit) throw updateError("download exceeds size limit", diagnose);
      if (write) write(chunk);
      else chunks.push(chunk);
    }
  }
  return Buffer.concat(chunks);
}
