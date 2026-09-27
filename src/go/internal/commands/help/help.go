package help

import (
	"context"
	"flag"
	"fmt"
	"io"
	"strings"

	"github.com/Soul-Brews-Studio/maw-cli/src/go/internal/command"
	"github.com/Soul-Brews-Studio/maw-cli/src/go/internal/commands/plugins"
)

type plugin struct{}

func init() { command.Register(func() command.CommandPlugin { return &plugin{} }) }
func (*plugin) Metadata() command.Metadata {
	return command.Metadata{Name: "help", Summary: "Show command help", Usage: "maw help [command]"}
}
func (*plugin) BindFlags(*flag.FlagSet) {}
func (*plugin) Run(ctx context.Context, i *command.Invocation) int {
	if len(i.Args) == 0 {
		root(i)
		return 0
	}
	if len(i.Args) != 1 {
		return i.Fail("usage: maw help [command]")
	}
	for _, cmd := range i.Commands {
		if cmd.Name != i.Args[0] {
			continue
		}
		if cmd.Path != "" {
			return i.Execute(ctx, cmd.Name, []string{"--help"})
		}
		fmt.Fprintf(i.Stdout, "Usage: %s\n\n%s\n", cmd.Usage, cmd.Summary)
		return 0
	}
	return i.Execute(ctx, i.Args[0], []string{"--help"})
}

// root prints built-ins, installed plugins and PATH executables as separate
// sections (#53). Installed plugins come from manifests only; nothing runs.
func root(i *command.Invocation) {
	columns := terminalWidth(i.Stdout)
	if columns <= 0 {
		columns = 80
	}
	fmt.Fprintln(i.Stdout, "Usage: maw <command> [args]\n\nCommands:")
	known := map[string]command.Metadata{}
	external := [][2]string{}
	for _, cmd := range i.Commands {
		known[cmd.Name] = cmd
		if cmd.Path != "" {
			external = append(external, [2]string{cmd.Name, "maw-" + cmd.Name})
		} else if cmd.Name != "plugins" {
			fmt.Fprintf(i.Stdout, "  %-12s %s\n", cmd.Name, cmd.Summary)
		}
	}
	installed, disabled, err := plugins.HelpPlugins(i.Stderr)
	if err != nil {
		fmt.Fprintf(i.Stderr, "maw: installed plugins not listed: %s\n  maw plugin ls\n", err)
	} else if len(installed) > 0 || disabled > 0 {
		rows := [][2]string{}
		for _, p := range installed {
			label, aliases := p.Command, []string{}
			for _, alias := range p.Aliases {
				if _, taken := known[alias]; !taken {
					aliases = append(aliases, alias)
				}
			}
			if len(aliases) > 0 {
				label += " (" + strings.Join(aliases, ", ") + ")"
			}
			summary := p.Summary
			if shadow, taken := known[p.Command]; taken {
				mark := "(shadowed by built-in)"
				if shadow.Path != "" {
					mark = "(shadowed by PATH maw-" + p.Command + ")"
				}
				summary = strings.TrimSpace(mark + " " + summary)
			}
			rows = append(rows, [2]string{label, summary})
		}
		fmt.Fprintln(i.Stdout, "\nInstalled plugins:")
		writeRows(i.Stdout, rows, columns)
		if disabled > 0 {
			fmt.Fprintf(i.Stdout, "  %d disabled — maw plugin ls --all\n", disabled)
		}
	}
	if len(external) > 0 {
		fmt.Fprintln(i.Stdout, "\nExternal (PATH):")
		writeRows(i.Stdout, external, columns)
	}
	fmt.Fprintln(i.Stdout, "\nRun 'maw help <command>' for command help.\nPlugins: executable maw-<command> files in absolute PATH directories.")
}

// writeRows aligns labels in one column and cuts each row to columns
// characters, ending a cut summary with an ellipsis.
func writeRows(out io.Writer, rows [][2]string, columns int) {
	width := 12
	for _, row := range rows {
		if len(row[0]) > width {
			width = len(row[0])
		}
	}
	for _, row := range rows {
		head := fmt.Sprintf("  %-*s", width, row[0])
		summary := []rune(row[1])
		room := columns - len(head) - 1
		switch {
		case len(summary) > 0 && len(summary) <= room:
			fmt.Fprintf(out, "%s %s\n", head, row[1])
		case len(summary) > 0 && room > 0:
			fmt.Fprintf(out, "%s %s…\n", head, string(summary[:room-1]))
		default:
			fmt.Fprintln(out, strings.TrimRight(head, " "))
		}
	}
}
