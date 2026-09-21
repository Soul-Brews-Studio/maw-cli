import type { Oracle } from "./types";

export type Resolution =
  | { kind: "found"; oracle: Oracle; how: "name" | "slug" | "prefix" | "substring" }
  | { kind: "none" }
  | { kind: "ambiguous"; candidates: Oracle[] };

const slug = (oracle: Oracle) => oracle.org && oracle.repo ? `${oracle.org}/${oracle.repo}` : "";

function only(matches: Oracle[], how: "name" | "slug" | "prefix" | "substring"): Resolution | null {
  if (matches.length === 1) return { kind: "found", oracle: matches[0]!, how };
  if (matches.length > 1) return { kind: "ambiguous", candidates: matches };
  return null;
}

export function resolveOracle(oracles: Oracle[], target: string): Resolution {
  const wanted = target.toLowerCase();
  return only(oracles.filter(o => o.name.toLowerCase() === wanted), "name")
    ?? only(oracles.filter(o => slug(o).toLowerCase() === wanted), "slug")
    ?? only(oracles.filter(o => o.name.toLowerCase().startsWith(wanted)), "prefix")
    ?? only(oracles.filter(o => o.name.toLowerCase().includes(wanted)), "substring")
    ?? { kind: "none" };
}
