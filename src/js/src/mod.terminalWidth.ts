// Columns of the terminal stdout writes to; 80 when stdout is not a terminal.
export function terminalWidth(): number {
  return process.stdout.isTTY && process.stdout.columns > 0 ? process.stdout.columns : 80;
}
