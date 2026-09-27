// Root help rows (#53): "  label  summary", labels padded to one column and
// each row cut to `columns` characters with a trailing ellipsis.
export function helpRows(rows: [string, string][], columns: number): string[] {
  const width = Math.max(12, ...rows.map(([label]) => label.length));
  return rows.map(([label, summary]) => {
    const head = `  ${label.padEnd(width)}`;
    if (!summary) return head.trimEnd();
    const room = columns - head.length - 1;
    const chars = Array.from(summary);
    if (chars.length <= room) return `${head} ${summary}`;
    return room > 0 ? `${head} ${chars.slice(0, room - 1).join("")}…` : head.trimEnd();
  });
}
