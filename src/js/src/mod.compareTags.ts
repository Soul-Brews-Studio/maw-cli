export const tagPattern = /^v([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{1,2})-alpha\.([0-9]{1,4})$/;

// Numeric order of two alpha CalVer tags; both must match tagPattern.
export function compareTags(a: string, b: string): number {
  const x = tagPattern.exec(a)!, y = tagPattern.exec(b)!;
  for (let n = 1; n <= 4; n++) {
    const order = Math.sign(Number(x[n]) - Number(y[n]));
    if (order) return order;
  }
  return 0;
}
