import { compareTags, tagPattern } from "./mod.compareTags";
import type { ReleasePlan } from "./types";

// maw-js embeds only a release CalVer tag or "dev", so Go's companion-tag and
// module pseudo-version branches (commit ancestry via the compare API) have no
// js counterpart; any other string is reported as unrecognized, as in Go.
export function updateStatus(current: string, plan: ReleasePlan, explicit: boolean): { install: boolean; status: string } {
  if (current === "dev") return { install: false, status: "dev build (check only)" };
  if (explicit) return { install: true, status: "explicit release selected" };
  if (tagPattern.test(current)) {
    const order = compareTags(plan.tag, current);
    if (order > 0) return { install: true, status: "update available" };
    if (order === 0) return { install: false, status: "already up to date" };
    return { install: false, status: "installed version is newer than published release" };
  }
  return { install: false, status: "unrecognized installed version; select --version explicitly" };
}
