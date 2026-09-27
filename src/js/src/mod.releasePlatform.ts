import type { ReleasePlatform } from "./types";

// Release asset names use Go's os/arch vocabulary; anything else has no prebuilt.
export function releasePlatform(): ReleasePlatform | undefined {
  const os = process.platform === "linux" || process.platform === "darwin" ? process.platform : undefined;
  const arch = process.arch === "x64" ? "amd64" : process.arch === "arm64" ? "arm64" : undefined;
  return os && arch ? { os, arch } : undefined;
}
