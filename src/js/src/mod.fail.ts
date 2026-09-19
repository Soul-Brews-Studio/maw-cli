export function fail(message: string): number {
  console.error(`maw: ${message}`);
  return 2;
}
