package plugins

import (
	"fmt"
	"io"
	"strings"
)

func render(out io.Writer, plugins []installed, verbose, all bool) {
	if len(plugins) == 0 {
		fmt.Fprintln(out, "no plugins installed")
		return
	}
	active, missing, cli, api := 0, 0, 0, 0
	tiers := [3]int{}
	names := []string{}
	for _, p := range plugins {
		if p.Enabled {
			active++
		}
		if !all && !p.Enabled {
			continue
		}
		if verbose {
			status := "enabled"
			if !p.Enabled {
				status = "disabled"
			}
			fmt.Fprintf(out, "%s\t%s\t%s\t%s\t%s\n", p.Name, p.Version, p.Tier, status, safePath(p.Dir))
		}
		names = append(names, p.Name)
		tiers[tierRank(p.Tier)]++
		if p.CLI {
			cli++
		}
		if p.API {
			api++
		}
		if p.Missing {
			missing++
		}
	}
	if verbose {
		return
	}
	noun := "plugins"
	if len(plugins) == 1 {
		noun = "plugin"
	}
	fmt.Fprintf(out, "%d %s (%d active, %d disabled)\n", len(plugins), noun, active, len(plugins)-active)
	fmt.Fprintf(out, "  core: %d · standard: %d · extra: %d\n", tiers[0], tiers[1], tiers[2])
	health := "ok"
	if missing > 0 {
		suffix := ""
		if missing != 1 {
			suffix = "s"
		}
		health = fmt.Sprintf("%d missing executable%s", missing, suffix)
	}
	fmt.Fprintf(out, "  cli: %d · api: %d · health: %s\n", cli, api, health)
	if len(names) > 0 {
		fmt.Fprintf(out, "  %s\n", strings.Join(names, " · "))
	}
	if !all && active != len(plugins) {
		fmt.Fprintln(out, "  disabled hidden by default — use --all to include")
	}
}
