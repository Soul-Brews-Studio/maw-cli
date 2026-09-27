//go:build darwin || linux

package help

import (
	"io"
	"os"
	"syscall"
	"unsafe"
)

// terminalWidth reports the columns of the terminal out writes to, or 0 when
// out is not a terminal.
func terminalWidth(out io.Writer) int {
	file, ok := out.(*os.File)
	if !ok {
		return 0
	}
	var size struct{ rows, columns, x, y uint16 }
	if _, _, errno := syscall.Syscall(syscall.SYS_IOCTL, file.Fd(), uintptr(syscall.TIOCGWINSZ), uintptr(unsafe.Pointer(&size))); errno != 0 {
		return 0
	}
	return int(size.columns)
}
