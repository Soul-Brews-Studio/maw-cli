const std = @import("std");
const V = std.json.Value;
const Object = std.json.ObjectMap;
const tiers = [_][]const u8{ "core", "standard", "extra" };
const Plugin = struct { name: []const u8, version: []const u8, tier: usize, dir: []const u8, enabled: bool, cli: bool, api: bool, missing: bool, command: []const u8, runtime: []const u8, target: []const u8, interactive: bool, entry: []const u8 };
const Config = struct { path: []const u8, name: []const u8, weight: []const u8, local: bool };
const Context = struct {
    a: std.mem.Allocator,
    io: std.Io,
    env: *const std.process.Environ.Map,

    fn out(c: Context, file: std.Io.File, comptime format: []const u8, args: anytype) !void {
        try file.writeStreamingAll(c.io, try std.fmt.allocPrint(c.a, format, args));
    }
    fn safe(c: Context, text: []const u8) ![]const u8 {
        var result: std.ArrayList(u8) = .empty;
        var i: usize = 0;
        while (i < text.len) : (i += 1) {
            const byte = text[i];
            if (byte < 32 or byte == 127) {
                try result.appendSlice(c.a, try std.fmt.allocPrint(c.a, "\\u{x:0>4}", .{@as(u16, byte)}));
            } else if (byte == 0xc2 and i + 1 < text.len and text[i + 1] >= 0x80 and text[i + 1] <= 0x9f) {
                i += 1;
                try result.appendSlice(c.a, try std.fmt.allocPrint(c.a, "\\u{x:0>4}", .{@as(u16, text[i])}));
            } else try result.append(c.a, byte);
        }
        return result.toOwnedSlice(c.a);
    }
    fn envOr(c: Context, name: []const u8, fallback: []const u8) []const u8 {
        if (c.env.get(name)) |value| {
            if (value.len > 0) return value;
        }
        return fallback;
    }
    fn join(c: Context, parts: []const []const u8) ![]const u8 {
        return std.fs.path.resolve(c.a, parts);
    }
    fn regular(c: Context, path: []const u8) bool {
        const stat = std.Io.Dir.cwd().statFile(c.io, path, .{}) catch return false;
        return stat.kind == .file;
    }
    fn read(c: Context, path: []const u8) !?Object {
        const dir = std.Io.Dir.cwd();
        const stat = dir.statFile(c.io, path, .{}) catch |err| {
            if (err == error.FileNotFound) return null;
            return err;
        };
        if (stat.kind != .file or stat.size > 1048576) return error.InvalidMetadataFile;
        var file = try dir.openFile(c.io, path, .{});
        defer file.close(c.io);
        const opened = try file.stat(c.io);
        if (opened.kind != .file or opened.size > 1048576) return error.InvalidMetadataFile;
        var reader = file.reader(c.io, &.{});
        const bytes = try reader.interface.allocRemaining(c.a, .limited(1048577));
        if (bytes.len > 1048576 or !std.unicode.utf8ValidateSlice(bytes)) return error.InvalidMetadataFile;
        const parsed = try std.json.parseFromSlice(V, c.a, bytes, .{ .duplicate_field_behavior = .use_last });
        if (parsed.value != .object) return error.ExpectedObject;
        return parsed.value.object;
    }
    fn entries(c: Context, root: []const u8) ![][]const u8 {
        var names: std.ArrayList([]const u8) = .empty;
        var dir = std.Io.Dir.cwd().openDir(c.io, root, .{ .iterate = true }) catch |err| {
            if (err == error.FileNotFound) return names.toOwnedSlice(c.a);
            return err;
        };
        defer dir.close(c.io);
        var iterator = dir.iterate();
        while (try iterator.next(c.io)) |entry| try names.append(c.a, try c.a.dupe(u8, entry.name));
        std.mem.sort([]const u8, names.items, {}, lessString);
        return names.toOwnedSlice(c.a);
    }
    fn paths(c: Context) !struct { plugins: []const u8, config: []const u8 } {
        const cwd = try std.process.currentPathAlloc(c.io, c.a);
        const home = c.envOr("HOME", c.envOr("USERPROFILE", ""));
        const xdg_value = c.envOr("MAW_XDG", "");
        const xdg = eql(xdg_value, "1") or std.ascii.eqlIgnoreCase(xdg_value, "true") or std.ascii.eqlIgnoreCase(xdg_value, "yes") or std.ascii.eqlIgnoreCase(xdg_value, "on");
        if (home.len == 0 and ((c.envOr("MAW_PLUGINS_DIR", "").len == 0 and c.envOr("MAW_HOME", "").len == 0 and c.envOr("MAW_DATA_DIR", "").len == 0 and !(xdg and c.envOr("XDG_DATA_HOME", "").len > 0)) or (c.envOr("MAW_HOME", "").len == 0 and c.envOr("MAW_CONFIG_DIR", "").len == 0 and c.envOr("XDG_CONFIG_HOME", "").len == 0))) return error.HomeNotSet;
        const fallback_data = if (xdg) try c.join(&.{ cwd, c.envOr("XDG_DATA_HOME", try c.join(&.{ home, ".local/share" })), "maw" }) else try c.join(&.{ cwd, home, ".maw" });
        const data = c.envOr("MAW_HOME", c.envOr("MAW_DATA_DIR", fallback_data));
        const plugin_root = c.envOr("MAW_PLUGINS_DIR", try c.join(&.{ cwd, data, "plugins" }));
        const maw_home = c.envOr("MAW_HOME", "");
        const config = if (maw_home.len > 0) try c.join(&.{ cwd, maw_home, "config" }) else c.envOr("MAW_CONFIG_DIR", try c.join(&.{ cwd, c.envOr("XDG_CONFIG_HOME", try c.join(&.{ home, ".config" })), "maw" }));
        return .{ .plugins = try c.join(&.{ cwd, plugin_root }), .config = try c.join(&.{ cwd, config }) };
    }
    fn disabled(c: Context, root: []const u8) !std.StringHashMap(void) {
        var files: std.ArrayList(Config) = .empty;
        for (try c.entries(root)) |name| {
            if (name.len <= 16 or !std.mem.startsWith(u8, name, "maw.config.") or !std.mem.endsWith(u8, name, ".json")) continue;
            var number = name[11 .. name.len - 5];
            const local = std.mem.endsWith(u8, number, ".local");
            if (local) number = number[0 .. number.len - 6];
            if (number.len == 0) continue;
            var valid = true;
            for (number) |b| {
                if (!std.ascii.isDigit(b)) valid = false;
            }
            if (!valid) continue;
            try files.append(c.a, .{ .path = try c.join(&.{ root, name }), .name = name, .weight = std.mem.trimStart(u8, number, "0"), .local = local });
        }
        std.mem.sort(Config, files.items, {}, lessConfig);
        if (files.items.len == 0) try files.append(c.a, .{ .path = try c.join(&.{ root, "maw.config.json" }), .name = "", .weight = "", .local = false });
        var result = std.StringHashMap(void).init(c.a);
        for (files.items) |file| {
            if (try c.read(file.path)) |object| {
                if (object.get("disabledPlugins")) |value| {
                    if (value == .array) {
                        result.clearRetainingCapacity();
                        for (value.array.items) |item| {
                            if (item == .string) try result.put(item.string, {});
                        }
                    }
                }
            }
        }
        return result;
    }
    fn parse(c: Context, m: Object, dir: []const u8, overrides: Object, off: std.StringHashMap(void)) !?Plugin {
        const name = string(m, "name");
        const version = string(m, "version");
        if (name.len == 0 or version.len == 0 or !eql(version, try c.safe(version))) return null;
        for (name) |b| {
            if (!std.ascii.isAlphanumeric(b) and b != '.' and b != '_' and b != '-') return null;
        }
        const explicit = string(m, "tier");
        var tier: ?usize = null;
        for (tiers, 0..) |t, i| {
            if (eql(t, explicit)) tier = i;
        }
        if (m.contains("tier") and tier == null) return null;
        if (m.contains("weight") and weight(m.get("weight")) == null) return null;
        const w = weight(overrides.get(name)) orelse weight(m.get("weight")) orelse 50;
        var entry = string(m, "entry");
        if (entry.len == 0 and !eql(string(m, "target"), "wasm")) {
            if (m.get("artifact")) |artifact| {
                if (artifact == .object) entry = string(artifact.object, "path");
            }
        }
        if (entry.len == 0) entry = string(m, "wasm");
        const cli = isObject(m.get("cli")) or entry.len > 0;
        var command: []const u8 = "";
        var interactive = false;
        if (m.get("cli")) |value| {
            if (value == .object) {
                command = string(value.object, "command");
                if (command.len == 0) command = name;
                if (value.object.get("interactive")) |flag| interactive = flag == .bool and flag.bool;
            }
        }
        const absolute_entry = if (entry.len == 0) "" else try c.join(&.{ dir, entry });
        return .{ .name = name, .version = version, .dir = dir, .tier = tier orelse (if (w < 10) @as(usize, 0) else if (w < 50) @as(usize, 1) else @as(usize, 2)), .enabled = !off.contains(name), .cli = cli, .api = isObject(m.get("api")), .missing = if (entry.len == 0) cli else !c.regular(absolute_entry), .command = command, .runtime = string(m, "runtime"), .target = string(m, "target"), .interactive = interactive, .entry = absolute_entry };
    }
    fn scan(c: Context, root: []const u8, off: std.StringHashMap(void)) ![]Plugin {
        const overrides = (try c.read(try c.join(&.{ root, ".overrides.json" }))) orelse Object.empty;
        var result: std.ArrayList(Plugin) = .empty;
        var seen = std.StringHashMap(void).init(c.a);
        for (try c.entries(root)) |name| {
            const dir = try c.join(&.{ root, name });
            const stat = std.Io.Dir.cwd().statFile(c.io, dir, .{}) catch continue;
            if (stat.kind != .directory) continue;
            const value = c.read(try c.join(&.{ dir, "plugin.json" })) catch {
                try c.out(.stderr(), "maw: skipped invalid plugin.json: {s}\n", .{try c.safe(dir)});
                continue;
            };
            if (value) |m| {
                if (try c.parse(m, dir, overrides, off)) |p| {
                    if (!seen.contains(p.name)) {
                        try seen.put(p.name, {});
                        try result.append(c.a, p);
                    }
                } else try c.out(.stderr(), "maw: skipped invalid plugin.json: {s}\n", .{try c.safe(dir)});
            } else {
                if (std.Io.Dir.cwd().statFile(c.io, try c.join(&.{ dir, "plugin.ts" }), .{})) |_| {
                    try c.out(.stderr(), "maw: skipped TypeScript-only manifest: {s}\n", .{try c.safe(dir)});
                } else |_| {}
            }
        }
        std.mem.sort(Plugin, result.items, {}, lessPlugin);
        return result.toOwnedSlice(c.a);
    }
    fn render(c: Context, plugins: []const Plugin, verbose: bool, all: bool) !void {
        if (plugins.len == 0) return c.out(.stdout(), "no plugins installed\n", .{});
        var active: usize = 0;
        var missing: usize = 0;
        var cli: usize = 0;
        var api: usize = 0;
        var counts = [_]usize{0} ** 3;
        var names: std.ArrayList([]const u8) = .empty;
        for (plugins) |p| {
            if (p.enabled) active += 1;
            if (!all and !p.enabled) continue;
            if (verbose) try c.out(.stdout(), "{s}\t{s}\t{s}\t{s}\t{s}\n", .{ p.name, p.version, tiers[p.tier], if (p.enabled) "enabled" else "disabled", try c.safe(p.dir) });
            try names.append(c.a, p.name);
            counts[p.tier] += 1;
            if (p.cli) cli += 1;
            if (p.api) api += 1;
            if (p.missing) missing += 1;
        }
        if (verbose) return;
        const health = if (missing == 0) "ok" else try std.fmt.allocPrint(c.a, "{d} missing executable{s}", .{ missing, if (missing == 1) "" else "s" });
        try c.out(.stdout(), "{d} plugin{s} ({d} active, {d} disabled)\n  core: {d} · standard: {d} · extra: {d}\n  cli: {d} · api: {d} · health: {s}\n", .{ plugins.len, if (plugins.len == 1) "" else "s", active, plugins.len - active, counts[0], counts[1], counts[2], cli, api, health });
        if (names.items.len > 0) try c.out(.stdout(), "  {s}\n", .{try std.mem.join(c.a, " · ", names.items)});
        if (!all and active != plugins.len) try c.out(.stdout(), "  disabled hidden by default — use --all to include\n", .{});
    }
};
fn eql(a: []const u8, b: []const u8) bool {
    return std.mem.eql(u8, a, b);
}
fn string(m: Object, key: []const u8) []const u8 {
    const value = m.get(key) orelse return "";
    return if (value == .string) value.string else "";
}
fn isObject(value: ?V) bool {
    return if (value) |v| v == .object else false;
}
fn weight(value: ?V) ?f64 {
    const v = value orelse return null;
    const n: f64 = switch (v) {
        .integer => @floatFromInt(v.integer),
        .float => v.float,
        else => return null,
    };
    return if (std.math.isFinite(n) and n >= 0 and n <= 99) n else null;
}
fn lessString(_: void, a: []const u8, b: []const u8) bool {
    return std.mem.lessThan(u8, a, b);
}
fn lessConfig(_: void, a: Config, b: Config) bool {
    if (a.weight.len != b.weight.len) return a.weight.len < b.weight.len;
    if (!eql(a.weight, b.weight)) return lessString({}, a.weight, b.weight);
    if (a.local != b.local) return !a.local;
    return lessString({}, a.name, b.name);
}
fn lessPlugin(_: void, a: Plugin, b: Plugin) bool {
    return if (a.tier != b.tier) a.tier < b.tier else lessString({}, a.name, b.name);
}

pub fn run(a: std.mem.Allocator, io: std.Io, env: *const std.process.Environ.Map, args: []const []const u8, legacy: bool) !u8 {
    const c = Context{ .a = a, .io = io, .env = env };
    var flags = args;
    var valid = true;
    if (args.len > 0 and eql(args[0], "ls")) {
        flags = args[1..];
    } else if (!legacy) {
        valid = false;
    }
    var verbose = false;
    var all = false;
    for (flags) |arg| {
        if ((eql(arg, "-v") or eql(arg, "--verbose")) and !verbose) {
            verbose = true;
        } else if (eql(arg, "--all") and !all) {
            all = true;
        } else {
            valid = false;
        }
    }
    if (!valid) {
        try c.out(.stderr(), "maw: usage: maw {s} [-v|--verbose] [--all]\n", .{if (legacy) "plugins [ls]" else "plugin ls"});
        return 2;
    }
    return execute(c, verbose, all) catch |err| {
        try c.out(.stderr(), "maw: plugin inventory: {s}\n", .{@errorName(err)});
        return 1;
    };
}
fn execute(c: Context, verbose: bool, all: bool) !u8 {
    const locations = try c.paths();
    const off = try c.disabled(locations.config);
    const plugins = try c.scan(locations.plugins, off);
    try c.render(plugins, verbose, all);
    return 0;
}

pub const Dispatch = union(enum) { failure: u8, argv: []const []const u8 };

pub fn resolve(a: std.mem.Allocator, io: std.Io, env: *const std.process.Environ.Map, name: []const u8, args: []const []const u8) !?Dispatch {
    if (name.len == 0 or name[0] < 'a' or name[0] > 'z') return null;
    for (name) |b| {
        if (!((b >= 'a' and b <= 'z') or std.ascii.isDigit(b) or b == '-')) return null;
    }
    for ([_][]const u8{ "go", "rs", "js", "zig", "index" }) |reserved| {
        if (eql(name, reserved)) return null;
    }
    const c = Context{ .a = a, .io = io, .env = env };
    return resolveInstalled(c, name, args) catch |err| {
        try c.out(.stderr(), "maw: plugin inventory: {s}\n", .{@errorName(err)});
        return Dispatch{ .failure = 1 };
    };
}

fn resolveInstalled(c: Context, name: []const u8, args: []const []const u8) !?Dispatch {
    const locations = try c.paths();
    const off = try c.disabled(locations.config);
    for (try c.scan(locations.plugins, off)) |p| {
        if (!eql(p.command, name)) continue;
        if (!p.enabled) {
            try c.out(.stderr(), "maw: plugin {s} is disabled\n", .{p.name});
            return Dispatch{ .failure = 1 };
        }
        if (!eql(p.runtime, "bun-dev") or !eql(p.target, "js") or !p.interactive) {
            try c.out(.stderr(), "maw: plugin {s} is not a standalone Bun CLI (requires runtime=bun-dev, target=js, cli.interactive=true)\n", .{p.name});
            return Dispatch{ .failure = 126 };
        }
        if (p.entry.len == 0 or !c.regular(p.entry)) {
            try c.out(.stderr(), "maw: plugin {s} entry is missing or not a regular file\n", .{p.name});
            return Dispatch{ .failure = 126 };
        }
        const bun = try findBun(c) orelse {
            try c.out(.stderr(), "maw: plugin {s} requires bun on PATH\n", .{p.name});
            return Dispatch{ .failure = 126 };
        };
        const argv = try c.a.alloc([]const u8, args.len + 2);
        argv[0] = bun;
        argv[1] = p.entry;
        @memcpy(argv[2..], args);
        return Dispatch{ .argv = argv };
    }
    return null;
}

fn findBun(c: Context) !?[]const u8 {
    var paths = std.mem.splitScalar(u8, c.envOr("PATH", ""), std.fs.path.delimiter);
    while (paths.next()) |directory| {
        if (!std.fs.path.isAbsolute(directory)) continue;
        const path = try c.join(&.{ directory, if (@import("builtin").os.tag == .windows) "bun.exe" else "bun" });
        if (!c.regular(path)) continue;
        if (@import("builtin").os.tag != .windows) {
            std.Io.Dir.cwd().access(c.io, path, .{ .execute = true }) catch continue;
        }
        return path;
    }
    return null;
}
