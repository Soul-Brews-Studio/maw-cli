export function safePath(path: string): string {
  return path.replace(/[\u0000-\u001f\u007f-\u009f]/g, c => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`);
}
