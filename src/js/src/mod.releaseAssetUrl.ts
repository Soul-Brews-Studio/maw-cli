import { downloadOrigin, repository } from "./mod.validReleaseUrl";

export function releaseAssetUrl(tag: string, name: string): string {
  return `${downloadOrigin}/${repository}/releases/download/${tag}/${name}`;
}
