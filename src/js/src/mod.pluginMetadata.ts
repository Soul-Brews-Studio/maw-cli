import { pluginGit } from "./mod.pluginGit";

export function pluginMetadata(dir: string, revision = "HEAD"): { name: string; version: string; entry: string; hash: string } {
  const manifestTree = pluginGit(dir, ["ls-tree", "-z", revision, "--", "plugin.json"]);
  if (!/^100(644|755) blob [0-9a-f]+\tplugin\.json\0$/.test(manifestTree)) throw new Error("plugin.json must be a committed regular file");
  const raw = pluginGit(dir, ["show", `${revision}:plugin.json`]);
  if (Buffer.byteLength(raw) > 1048576) throw new Error("plugin.json is too large");
  const m = JSON.parse(raw);
  if (!m || typeof m !== "object" || Array.isArray(m) || typeof m.name !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(m.name) || typeof m.version !== "string" || !m.version || /[\x00-\x1f\x7f-\x9f]/.test(m.version)) throw new Error("invalid plugin name or version");
  const entry = m.entry || m.artifact?.path || m.wasm;
  if (typeof entry !== "string" || !entry || entry.includes("\\") || /[\x00-\x1f\x7f-\x9f]/.test(entry) || entry.split("/").some((part: string) => !part || part === "." || part === "..")) throw new Error("unsafe plugin entry");
  const tree = pluginGit(dir, ["ls-tree", "-z", revision, "--", entry]);
  const match = /^100(?:644|755) blob ([0-9a-f]+)\t([^\0]+)\0$/.exec(tree);
  if (!match || match[2] !== entry) throw new Error("plugin entry must be a committed regular file");
  return { name: m.name, version: m.version, entry, hash: match[1] };
}
