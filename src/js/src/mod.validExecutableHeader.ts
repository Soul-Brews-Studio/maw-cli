import type { ReleasePlatform } from "./types";

// First 32 bytes: a 64-bit little-endian ELF executable/PIE for Linux, or a
// 64-bit Mach-O MH_EXECUTE for macOS, of this machine's architecture.
export function validExecutableHeader(header: Uint8Array, platform: ReleasePlatform): boolean {
  const view = new DataView(header.buffer, header.byteOffset, header.byteLength);
  if (platform.os === "linux") {
    const machine = platform.arch === "arm64" ? 183 : 62;
    const kind = view.getUint16(16, true);
    return [127, 69, 76, 70, 2, 1, 1].every((byte, n) => header[n] === byte) && (kind === 2 || kind === 3) && view.getUint16(18, true) === machine;
  }
  const cpu = platform.arch === "arm64" ? 0x0100000c : 0x01000007;
  return [0xcf, 0xfa, 0xed, 0xfe].every((byte, n) => header[n] === byte) && view.getUint32(4, true) === cpu && view.getUint32(12, true) === 2;
}
