// Origins are constants; update-smoke.py rewrites them only in an overlay copy
// of this file. Production has no test URL switch.
export const apiOrigin = "https://api.github.com";
export const downloadOrigin = "https://github.com";
export const repository = "Soul-Brews-Studio/maw-cli";
const assetHosts = ["release-assets.githubusercontent.com", "objects.githubusercontent.com", "objects-origin.githubusercontent.com", "github-releases.githubusercontent.com"];

export function validReleaseUrl(raw: string): boolean {
  let url: URL;
  try { url = new URL(raw); } catch { return false; }
  if (url.protocol !== "https:" || url.username || url.password || url.hash) return false;
  if ([apiOrigin, downloadOrigin].some(origin => new URL(origin).host === url.host)) return true;
  if (url.port !== "" && url.port !== "443") return false;
  return assetHosts.includes(url.hostname);
}
