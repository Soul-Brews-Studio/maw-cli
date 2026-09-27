const std = @import("std");
const builtin = @import("builtin");
const build_options = @import("build_options");
const registry = @import("registry.zig");
const lifecycle = @import("lifecycle.zig");
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

    // Aligns labels in one column and cuts each row to `columns` characters,
    // ending a cut summary with an ellipsis.
    fn rows(self: Host, entries: []const [2][]const u8, columns: usize) !void {
        var width: usize = 12;
        for (entries) |entry| width = @max(width, entry[0].len);
        for (entries) |entry| {
            const head = try std.fmt.allocPrint(self.allocator, "  {s}", .{entry[0]});
            const padding = try self.allocator.alloc(u8, width - entry[0].len);
            @memset(padding, ' ');
            const characters = std.unicode.utf8CountCodepoints(entry[1]) catch entry[1].len;
            const room = columns -| (head.len + padding.len + 1);
            if (characters > 0 and characters <= room) {
                try self.output(.stdout(), "{s}{s} {s}\n", .{ head, padding, entry[1] });
            } else if (characters > 0 and room > 0) {
                var end: usize = 0;
                var kept: usize = 0;
                while (kept < room - 1) : (kept += 1) end += std.unicode.utf8ByteSequenceLength(entry[1][end]) catch 1;
                try self.output(.stdout(), "{s}{s} {s}\u{2026}\n", .{ head, padding, entry[1][0..end] });
            } else try self.output(.stdout(), "{s}\n", .{head});
        }
    }

    // Built-ins, installed plugins and PATH executables as separate sections
    // (#53). Installed plugins come from manifests only; nothing runs.
    fn rootHelp(self: Host) !void {
        const columns = terminalWidth();
        try self.output(.stdout(), "Usage: maw <command> [args]\n\nCommands:\n", .{});
        var external: std.ArrayList([2][]const u8) = .empty;
        for (self.commands) |command| {
            if (command.kind == .external) {
                try external.append(self.allocator, .{ command.name, try std.fmt.allocPrint(self.allocator, "maw-{s}", .{command.name}) });
            } else if (!eql(command.name, "plugins")) {
                try self.output(.stdout(), "  {s: <12} {s}\n", .{ command.name, command.summary });
            }
        }
        if (inventory.helpPlugins(self.allocator, self.io, self.env)) |listed| {
            if (listed.plugins.len > 0 or listed.disabled > 0) {
                var entries: std.ArrayList([2][]const u8) = .empty;
                for (listed.plugins) |p| {
                    var aliases: std.ArrayList([]const u8) = .empty;
                    for (p.aliases) |alias| {
                        if (registry.find(self.commands, alias) == null) try aliases.append(self.allocator, alias);
                    }
                    const label = if (aliases.items.len == 0) p.command else try std.fmt.allocPrint(self.allocator, "{s} ({s})", .{ p.command, try std.mem.join(self.allocator, ", ", aliases.items) });
                    var summary = p.summary;
                    if (registry.find(self.commands, p.command)) |shadow| {
                        const mark = if (shadow.kind == .external) try std.fmt.allocPrint(self.allocator, "(shadowed by PATH maw-{s})", .{p.command}) else "(shadowed by built-in)";
                        summary = if (summary.len == 0) mark else try std.fmt.allocPrint(self.allocator, "{s} {s}", .{ mark, summary });
                    }
                    try entries.append(self.allocator, .{ label, summary });
                }
                try self.output(.stdout(), "\nInstalled plugins:\n", .{});
                try self.rows(entries.items, columns);
                if (listed.disabled > 0) try self.output(.stdout(), "  {d} disabled \u{2014} maw plugin ls --all\n", .{listed.disabled});
            }
        } else |err| {
            try self.output(.stderr(), "maw: installed plugins not listed: {s}\n  maw plugin ls\n", .{@errorName(err)});
        }
        if (external.items.len > 0) {
            try self.output(.stdout(), "\nExternal (PATH):\n", .{});
            try self.rows(external.items, columns);
        }
        try self.output(.stdout(), "\nRun 'maw help <command>' for command help.\nPlugins: executable maw-<command> files in absolute PATH directories.\n", .{});
    }

    fn help(self: Host, args: []const []const u8) !u8 {
        if (args.len == 0) {
            try self.rootHelp();
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
            .answered => 0,
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
            .plugins => return lifecycle.run(self.allocator, self.io, self.env, args[1..], eql(name, "plugins")),
            .marketplace => {
                if (args.len > 2 or (args.len == 2 and !eql(args[1], "ls") and !eql(args[1], "list"))) return self.fail("usage: maw marketplace [ls|list]");
                try self.output(.stdout(), "NAME\tSOURCE\nherdr\thttps://github.com/Soul-Brews-Studio/maw-herdr-plugin\n", .{});
            },
        }
        return 0;
    }
};

// Columns of the terminal on stdout; 80 when stdout is not a terminal. ioctl is
// called directly: through std.Io's device_io_control, the ReleaseFast build
// never saw the kernel's write and always answered 80.
fn terminalWidth() usize {
    var size: std.posix.winsize = .{ .row = 0, .col = 0, .xpixel = 0, .ypixel = 0 };
    const ok = switch (builtin.os.tag) {
        .linux => std.os.linux.errno(std.os.linux.ioctl(1, std.os.linux.T.IOCGWINSZ, @intFromPtr(&size))) == .SUCCESS,
        .macos => std.c.ioctl(1, @bitCast(@as(u32, std.c.T.IOCGWINSZ)), &size) == 0,
        else => false,
    };
    return if (ok and size.col > 0) size.col else 80;
}

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
