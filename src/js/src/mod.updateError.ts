import type { UpdateError } from "./types";

export function updateError(message: string, ...fix: string[]): UpdateError {
  return Object.assign(new Error(message), { fix });
}
