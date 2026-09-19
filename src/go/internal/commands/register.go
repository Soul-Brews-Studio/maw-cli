// Package commands links built-ins that register their own factories.
package commands

import (
	_ "github.com/Soul-Brews-Studio/maw-cli/src/go/internal/commands/context"
	_ "github.com/Soul-Brews-Studio/maw-cli/src/go/internal/commands/help"
	_ "github.com/Soul-Brews-Studio/maw-cli/src/go/internal/commands/plugins"
	_ "github.com/Soul-Brews-Studio/maw-cli/src/go/internal/commands/version"
)
