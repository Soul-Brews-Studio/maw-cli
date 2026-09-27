//go:build !darwin && !linux

package help

import "io"

// terminalWidth is not measured here; root help falls back to 80 columns.
func terminalWidth(io.Writer) int { return 0 }
