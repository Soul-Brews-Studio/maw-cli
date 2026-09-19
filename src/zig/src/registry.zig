const std = @import("std");
const builtin = @import("builtin");

pub const Kind = enum { help, version, plugins, marketplace, external };
pub const Command = struct {
    name: []const u8,
    summary: []const u8,
    usage: []const u8 = "",
    path: []const u8 = "",
    kind: Kind,
};

pub fn find(commands: []const Command, name: []const u8) ?Command {
    for (commands) |command| {
        if (std.mem.eql(u8, command.name, name)) return command;
    }
    return null;
}

fn validName(name: []const u8) bool {
    if (name.len == 0 or name[0] < 'a' or name[0] > 'z') return false;
    for (name) |c| {
        if (!((c >= 'a' and c <= 'z') or (c >= '0' and c <= '9') or c == '-')) return false;
    }
    return true;
}

fn lessThan(_: void, a: Command, b: Command) bool {
    return std.mem.lessThan(u8, a.name, b.name);
}

pub fn discover(allocator: std.mem.Allocator, io: std.Io, path: []const u8) ![]Command {
    var commands: std.ArrayList(Command) = .empty;
    try commands.appendSlice(allocator, &.{
        .{ .name = "help", .summary = "Show command help", .usage = "maw help [command]", .kind = .help },
        .{ .name = "version", .summary = "Show maw version", .usage = "maw version", .kind = .version },
        .{ .name = "plugin", .summary = "Manage installed plugins", .usage = "maw plugin <ls|list|install|update|info|check> [args]", .kind = .plugins },
        .{ .name = "plugins", .summary = "Alias for plugin ls", .usage = "maw plugins [ls] [-v|--verbose] [--all]", .kind = .plugins },
        .{ .name = "marketplace", .summary = "List known plugin repositories", .usage = "maw marketplace [ls|list]", .kind = .marketplace },
    });
    var paths = std.mem.splitScalar(u8, path, std.fs.path.delimiter);
    while (paths.next()) |directory| {
        if (!std.fs.path.isAbsolute(directory)) continue;
        var dir = std.Io.Dir.cwd().openDir(io, directory, .{ .iterate = true }) catch continue;
        defer dir.close(io);
        var entries = dir.iterate();
        while (entries.next(io) catch null) |entry| {
            var name = entry.name;
            if (builtin.os.tag == .windows) {
                if (!std.mem.endsWith(u8, name, ".exe")) continue;
                name = name[0 .. name.len - 4];
            }
            if (!std.mem.startsWith(u8, name, "maw-")) continue;
            name = name[4..];
            if (!validName(name) or std.mem.eql(u8, name, "go") or std.mem.eql(u8, name, "rs") or
                std.mem.eql(u8, name, "js") or std.mem.eql(u8, name, "zig") or find(commands.items, name) != null) continue;
            const candidate = try std.fs.path.join(allocator, &.{ directory, entry.name });
            defer allocator.free(candidate);
            const resolved = std.Io.Dir.cwd().realPathFileAlloc(io, candidate, allocator) catch continue;
            const stat = std.Io.Dir.cwd().statFile(io, resolved, .{}) catch {
                allocator.free(resolved);
                continue;
            };
            if (stat.kind != .file) {
                allocator.free(resolved);
                continue;
            }
            if (builtin.os.tag != .windows) {
                std.Io.Dir.cwd().access(io, resolved, .{ .execute = true }) catch {
                    allocator.free(resolved);
                    continue;
                };
            }
            try commands.append(allocator, .{ .name = try allocator.dupe(u8, name), .summary = "External plugin", .path = resolved, .kind = .external });
        }
    }
    std.mem.sort(Command, commands.items, {}, lessThan);
    return commands.toOwnedSlice(allocator);
}
