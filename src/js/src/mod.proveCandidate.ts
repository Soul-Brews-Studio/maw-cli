import { spawnSync } from "node:child_process";
import { dirname } from "node:path";
import { updateError } from "./mod.updateError";

// Run the unpacked candidate's own `version` with an empty PATH, a private HOME,
// a short deadline and bounded output; it must print exactly the target tag.
export function proveCandidate(path: string, tag: string): void {
  const result = spawnSync(path, ["version"], { cwd: dirname(path), env: { PATH: "", HOME: dirname(path) }, timeout: 5000, maxBuffer: 4096, encoding: "utf8" });
  const failed = (reason: string) => updateError(`candidate version check failed; original executable unchanged: ${reason}`);
  if (result.error) {
    const code = (result.error as NodeJS.ErrnoException).code;
    throw failed(code === "ENOBUFS" ? "candidate version output too large" : code === "ETIMEDOUT" ? "timed out after 5s" : result.error.message);
  }
  if (result.status !== 0) throw failed(result.signal ? `signal: ${result.signal}` : `exit status ${result.status}`);
  if (result.stdout !== `maw ${tag}\n` || result.stderr !== "") throw updateError("candidate version mismatch; original executable unchanged");
}
