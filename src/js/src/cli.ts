#!/usr/bin/env bun
import { run } from "./mod.run";

export { run };

if (import.meta.main) process.exitCode = await run(Bun.argv.slice(2));
