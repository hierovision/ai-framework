/**
 * Delegation sentinel — no-op server part.
 *
 * 2.1.4's loader only accepts a plugin directory that resolves a server
 * entrypoint; the sentinel's work is entirely in `tui.tsx`, so this part
 * defines the plugin id and does nothing else.
 */
import { SENTINEL_ID } from "./sentinel.ts";

export function createDefinition(Plugin: any) {
  return {
    id: SENTINEL_ID,
    async setup() {
      return () => {};
    },
  };
}

let Plugin: any = { define: (definition: any) => definition };
try {
  const mod: any = await import("@opencode/plugin");
  Plugin = mod.Plugin ?? mod.default ?? Plugin;
} catch {
  // The package is the runtime dependency; tests never import this module.
}

export default Plugin.define(createDefinition(Plugin));
