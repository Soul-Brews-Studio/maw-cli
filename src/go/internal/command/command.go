// Package command defines built-in commands and their init-time registration.
package command

import (
	"context"
	"flag"
	"fmt"
	"io"
)

type Metadata struct{ Name, Summary, Usage, Path string }
type CommandPlugin interface {
	Metadata() Metadata
	BindFlags(*flag.FlagSet)
	Run(context.Context, *Invocation) int
}
type Invocation struct {
	Args           []string
	Stdin          io.Reader
	Stdout, Stderr io.Writer
	Version        string
	Commands       []Metadata
	Execute        func(context.Context, string, []string) int
}

func (i *Invocation) Fail(message string) int { fmt.Fprintln(i.Stderr, "maw:", message); return 2 }

type Factory func() CommandPlugin

var factories = map[string]Factory{}

// Register is called only by command package init functions, before dispatch.
func Register(factory Factory) {
	name := factory().Metadata().Name
	if name == "" || factories[name] != nil {
		panic("invalid or duplicate command registration: " + name)
	}
	factories[name] = factory
}

// Factories returns a copy; dispatch creates a fresh instance from each factory.
func Factories() map[string]Factory {
	result := make(map[string]Factory, len(factories))
	for name, factory := range factories {
		result[name] = factory
	}
	return result
}
