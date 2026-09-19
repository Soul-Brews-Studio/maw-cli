import { resolve } from "node:path";

export function inventoryPaths(): { plugins: string; config: string } {
  const e = process.env, home = e.HOME || e.USERPROFILE || "";
  const xdg = ["1", "true", "yes", "on"].includes((e.MAW_XDG || "").toLowerCase());
  if (!home && ((!e.MAW_PLUGINS_DIR && !e.MAW_HOME && !e.MAW_DATA_DIR && !(xdg && e.XDG_DATA_HOME)) ||
      (!e.MAW_HOME && !e.MAW_CONFIG_DIR && !e.XDG_CONFIG_HOME))) throw new Error("HOME is not set; provide explicit plugin and config roots");
  const data = e.MAW_HOME || e.MAW_DATA_DIR || (xdg ? resolve(e.XDG_DATA_HOME || resolve(home, ".local/share"), "maw") : resolve(home, ".maw"));
  return {
    plugins: resolve(e.MAW_PLUGINS_DIR || resolve(data, "plugins")),
    config: resolve(e.MAW_HOME ? resolve(e.MAW_HOME, "config") : e.MAW_CONFIG_DIR || resolve(e.XDG_CONFIG_HOME || resolve(home, ".config"), "maw")),
  };
}
