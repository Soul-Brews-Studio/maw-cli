const std = @import("std");
const build_options = @import("build_options");
const registry = @import("registry.zig");
const inventory = @import("inventory.zig");

const Host = struct {
    allocator: std.mem.Allocator,
    io: std.Io,
    commands: []const registry.Command,
    env: *const std.process.Environ.Map,

    fn output(self: Host, file: std.Io.File, comptime format: []const u8, args: anytype) !void {
        const text = try std.fmt.allocPrint(self.allocator, format, args);
        defer self.allocator.free(text);
        try file.writeStreamingAll(self.io, text);
    }

    fn fail(self: Host, message: []const u8) !u8 {
        try self.output(.stderr(), "maw: {s}\n", .{message});
        return 2;
    }

    fn unknown(self: Host, name: []const u8) !u8 {
        try self.output(.stderr(), "maw: unknown command \"{s}\"; run 'maw help'\n", .{name});
        return 2;
    }

    fn help(self: Host, args: []const []const u8) !u8 {
        if (args.len == 0) {
            try self.output(.stdout(), "Usage: maw <command> [args]\n\nCommands:\n", .{});
            for (self.commands) |command| {
                try self.output(.stdout(), "  {s: <12} {s}\n", .{ command.name, command.summary });
            }
            try self.output(.stdout(), "\nRun 'maw help <command>' for command help.\nPlugins: executable maw-<command> files in absolute PATH directories.\n", .{});
            return 0;
        }
        if (args.len != 1) return self.fail("usage: maw help [command]");
        const command = registry.find(self.commands, args[0]) orelse return self.installed(args[0], &.{"--help"});
        if (command.kind == .external) return self.execute(command.path, &.{"--help"});
        try self.output(.stdout(), "Usage: {s}\n\n{s}\n", .{ command.usage, command.summary });
        return 0;
    }

    fn installed(self: Host, name: []const u8, args: []const []const u8) !u8 {
        const result = try inventory.resolve(self.allocator, self.io, self.env, name, args) orelse return self.unknown(name);
        return switch (result) {
            .failure => |code| code,
            .argv => |argv| self.execute(argv[0], argv[1..]),
        };
    }

    fn execute(self: Host, path: []const u8, args: []const []const u8) !u8 {
        const argv = try self.allocator.alloc([]const u8, args.len + 1);
        argv[0] = path;
        @memcpy(argv[1..], args);
        var child = std.process.spawn(self.io, .{ .argv = argv, .stdin = .inherit, .stdout = .inherit, .stderr = .inherit }) catch |err| {
            try self.output(.stderr(), "maw: cannot execute {s}: {s}\n", .{ path, @errorName(err) });
            return 126;
        };
        const term = child.wait(self.io) catch |err| {
            try self.output(.stderr(), "maw: cannot wait for {s}: {s}\n", .{ path, @errorName(err) });
            return 126;
        };
        return switch (term) {
            .exited => |status| @intCast(status),
            else => 1,
        };
    }

    fn run(self: Host, args: []const []const u8) !u8 {
        if (args.len == 0) return self.help(&.{});
        var name = args[0];
        const help_flag = eql(name, "-h") or eql(name, "--help");
        const version_flag = eql(name, "-v") or eql(name, "--version");
        if ((help_flag or version_flag) and args.len != 1) return self.fail("global help/version flags do not accept arguments");
        if (help_flag) name = "help";
        if (version_flag) name = "version";
        const command = registry.find(self.commands, name) orelse return self.installed(name, args[1..]);
        if (command.kind != .external and args.len == 2 and (eql(args[1], "-h") or eql(args[1], "--help"))) return self.help(&.{name});
        switch (command.kind) {
            .help => return self.help(args[1..]),
            .external => return self.execute(command.path, args[1..]),
            .version => {
                if (args.len != 1) return self.fail("usage: maw version");
                try self.output(.stdout(), "maw {s}\n", .{build_options.version});
            },
            .plugins => return inventory.run(self.allocator, self.io, self.env, args[1..], eql(name, "plugins")),
        }
        return 0;
    }
};

fn eql(a: []const u8, b: []const u8) bool {
    return std.mem.eql(u8, a, b);
}

pub fn main(init: std.process.Init) !void {
    const allocator = init.arena.allocator();
    const args = try init.minimal.args.toSlice(allocator);
    const host: Host = .{
        .allocator = allocator,
        .io = init.io,
        .env = init.environ_map,
        .commands = try registry.discover(allocator, init.io, init.environ_map.get("PATH") orelse ""),
    };
    std.process.exit(try host.run(args[1..]));
}
