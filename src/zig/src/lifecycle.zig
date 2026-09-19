const std = @import("std");
const inventory = @import("inventory.zig");
extern "c" fn renamex_np(old: [*:0]const u8, new: [*:0]const u8, flags: c_uint) c_int;
const Meta = struct { name: []const u8, entry: []const u8 };
fn eql(a: []const u8, b: []const u8) bool {
    return std.mem.eql(u8, a, b);
}
fn safeName(s: []const u8) bool {
    if (s.len == 0 or !std.ascii.isAlphanumeric(s[0])) return false;
    for (s) |b| if (!std.ascii.isAlphanumeric(b) and b != '-' and b != '_' and b != '.') return false;
    return true;
}
fn text(v: std.json.Value, key: []const u8) []const u8 {
    if (v != .object) return "";
    const item = v.object.get(key) orelse return "";
    return if (item == .string) item.string else "";
}
const Context = struct {
    a: std.mem.Allocator,
    io: std.Io,
    env: *const std.process.Environ.Map,
    fn join(c: Context, parts: []const []const u8) ![]const u8 {
        return std.fs.path.join(c.a, parts);
    }
    fn out(c: Context, comptime fmt: []const u8, args: anytype) !void {
        try std.Io.File.stdout().writeStreamingAll(c.io, try std.fmt.allocPrint(c.a, fmt, args));
    }
    fn git(c: Context, dir: []const u8, args: []const []const u8) ![]const u8 {
        var env = std.process.Environ.Map.init(c.a);
        var it = c.env.iterator();
        while (it.next()) |e| if (!std.mem.startsWith(u8, e.key_ptr.*, "GIT_")) {
            try env.put(e.key_ptr.*, e.value_ptr.*);
        };
        try env.put("GIT_CONFIG_GLOBAL", "/dev/null");
        try env.put("GIT_CONFIG_SYSTEM", "/dev/null");
        try env.put("GIT_CONFIG_NOSYSTEM", "1");
        try env.put("GIT_TERMINAL_PROMPT", "0");
        try env.put("GIT_LFS_SKIP_SMUDGE", "1");
        var argv: std.ArrayList([]const u8) = .empty;
        try argv.appendSlice(c.a, &.{ "git", "--literal-pathspecs", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "user.name=maw", "-c", "user.email=maw@localhost", "-c", "protocol.ext.allow=never" });
        try argv.appendSlice(c.a, args);
        const result = try std.process.run(c.a, c.io, .{ .argv = argv.items, .cwd = .{ .path = dir }, .environ_map = &env, .stdout_limit = .limited(1048577), .stderr_limit = .limited(65536) });
        if (result.term != .exited or result.term.exited != 0) {
            const detail = result.stderr[0..@min(result.stderr.len, 4096)];
            if (detail.len > 0) {
                const safe = try c.a.dupe(u8, detail);
                for (safe) |*byte| if ((byte.* < 32 and byte.* != '\n' and byte.* != '\t') or byte.* == 127) {
                    byte.* = '?';
                };
                try std.Io.File.stderr().writeStreamingAll(c.io, safe);
                if (safe[safe.len - 1] != '\n') try std.Io.File.stderr().writeStreamingAll(c.io, "\n");
            }
            return error.GitFailed;
        }
        return std.mem.trim(u8, result.stdout, "\r\n");
    }
    fn regular(c: Context, dir: []const u8, relative: []const u8) !void {
        if (relative.len == 0 or std.fs.path.isAbsolute(relative) or std.mem.indexOfScalar(u8, relative, '\\') != null) return error.UnsafeEntry;
        var parts = std.mem.splitScalar(u8, relative, '/');
        var path = dir;
        while (parts.next()) |part| {
            if (part.len == 0 or eql(part, ".") or eql(part, "..")) return error.UnsafeEntry;
            path = try c.join(&.{ path, part });
            const stat = try std.Io.Dir.cwd().statFile(c.io, path, .{ .follow_symlinks = false });
            if (stat.kind == .sym_link) return error.UnsafeEntry;
        }
        if ((try std.Io.Dir.cwd().statFile(c.io, path, .{})).kind != .file) return error.UnsafeEntry;
    }
    fn metadata(c: Context, bytes: []const u8) !Meta {
        if (bytes.len > 1048576) return error.InvalidMetadata;
        const parsed = try std.json.parseFromSlice(std.json.Value, c.a, bytes, .{});
        const v = parsed.value;
        const name = text(v, "name");
        const version = text(v, "version");
        if (!safeName(name) or version.len == 0) return error.InvalidMetadata;
        for (version) |b| if (b < 32 or b == 127) return error.InvalidMetadata;
        var entry = text(v, "entry");
        if (entry.len == 0 and v == .object) {
            if (v.object.get("artifact")) |artifact| entry = text(artifact, "path");
        }
        if (entry.len == 0) entry = text(v, "wasm");
        if (entry.len == 0 or std.fs.path.isAbsolute(entry) or std.mem.indexOfScalar(u8, entry, '\\') != null) return error.UnsafeEntry;
        for (entry) |b| if (b < 32 or b == 127) return error.UnsafeEntry;
        var parts = std.mem.splitScalar(u8, entry, '/');
        while (parts.next()) |p| {
            if (p.len == 0 or eql(p, ".") or eql(p, "..")) return error.UnsafeEntry;
        }
        return .{ .name = name, .entry = entry };
    }
    fn treeFile(c: Context, dir: []const u8, commit: []const u8, entry: []const u8) !void {
        const line = try c.git(dir, &.{ "ls-tree", "-z", commit, "--", entry });
        if (!std.mem.startsWith(u8, line, "100644 blob ") and !std.mem.startsWith(u8, line, "100755 blob ")) return error.UnsafeEntry;
        const end = std.mem.indexOfScalar(u8, line, 0) orelse return error.UnsafeEntry;
        if (end != line.len - 1) return error.UnsafeEntry;
        const tab = std.mem.indexOfScalar(u8, line[0..end], '\t') orelse return error.UnsafeEntry;
        if (!eql(line[tab + 1 .. end], entry)) return error.UnsafeEntry;
    }
    fn candidate(c: Context, dir: []const u8, commit: []const u8) !Meta {
        try c.treeFile(dir, commit, "plugin.json");
        const m = try c.metadata(try c.git(dir, &.{ "show", try std.fmt.allocPrint(c.a, "{s}:plugin.json", .{commit}) }));
        try c.treeFile(dir, commit, m.entry);
        return m;
    }
    fn current(c: Context, dir: []const u8) !Meta {
        try c.regular(dir, "plugin.json");
        var f = try std.Io.Dir.cwd().openFile(c.io, try c.join(&.{ dir, "plugin.json" }), .{});
        defer f.close(c.io);
        var reader = f.reader(c.io, &.{});
        const m = try c.metadata(try reader.interface.allocRemaining(c.a, .limited(1048577)));
        try c.regular(dir, m.entry);
        return m;
    }
    fn checkout(c: Context, root: []const u8, name: []const u8) ![]const u8 {
        if (!safeName(name)) return error.InvalidName;
        const dir = try c.join(&.{ root, name });
        if ((try std.Io.Dir.cwd().statFile(c.io, dir, .{ .follow_symlinks = false })).kind != .directory) return error.NotManagedCheckout;
        if ((try std.Io.Dir.cwd().statFile(c.io, try c.join(&.{ dir, ".git" }), .{ .follow_symlinks = false })).kind != .directory) return error.NotManagedCheckout;
        const real = try std.Io.Dir.cwd().realPathFileAlloc(c.io, dir, c.a);
        if (!eql(real, try c.git(dir, &.{ "rev-parse", "--show-toplevel" }))) return error.NotManagedCheckout;
        return dir;
    }
    fn fetchRef(c: Context, dir: []const u8, ref: []const u8) ![]const u8 {
        if (ref.len == 0 or ref[0] == '-' or ref[0] == '+') return error.InvalidRef;
        for (ref) |b| if (!std.ascii.isAlphanumeric(b) and b != '-' and b != '_' and b != '.' and b != '/') return error.InvalidRef;
        _ = try c.git(dir, &.{ "check-ref-format", "--allow-onelevel", ref });
        _ = try c.git(dir, &.{ "fetch", "--no-tags", "--no-recurse-submodules", "origin", ref });
        const commit = try c.git(dir, &.{ "rev-parse", "--verify", "FETCH_HEAD^{commit}" });
        var full = ref.len == 40;
        for (ref) |b| {
            if (!std.ascii.isHex(b)) full = false;
        }
        if (full and !std.ascii.eqlIgnoreCase(ref, commit)) return error.CommitMismatch;
        return commit;
    }
    fn publish(c: Context, stage: []const u8, destination: []const u8) !void {
        // Zig 0.16 renamePreserve uses hard links on macOS, which cannot move
        // directories. Darwin's RENAME_EXCL provides atomic no-overwrite rename.
        if (@import("builtin").os.tag == .macos) {
            const old = try c.a.dupeZ(u8, stage);
            const new = try c.a.dupeZ(u8, destination);
            while (true) switch (std.c.errno(renamex_np(old, new, 0x00000004))) {
                .SUCCESS => return,
                .INTR => continue,
                .EXIST, .NOTEMPTY => return error.PathAlreadyExists,
                .ACCES => return error.AccessDenied,
                .PERM => return error.PermissionDenied,
                else => |err| {
                    try std.Io.File.stderr().writeStreamingAll(c.io, try std.fmt.allocPrint(c.a, "maw: publishing plugin: {s}\n", .{@tagName(err)}));
                    return error.RenameFailed;
                },
            };
        }
        try std.Io.Dir.cwd().renamePreserve(stage, std.Io.Dir.cwd(), destination, c.io);
    }
    fn install(c: Context, root: []const u8, input: []const u8, explicit_ref: ?[]const u8) !u8 {
        var source = input;
        var ref = explicit_ref;
        const cwd = try std.process.currentPathAlloc(c.io, c.a);
        const local = std.Io.Dir.cwd().realPathFileAlloc(c.io, source, c.a) catch null;
        if (local) |path| {
            source = path;
        } else {
            if (std.mem.lastIndexOfScalar(u8, source, '@')) |at| {
                if (ref != null) return error.InvalidRef;
                ref = source[at + 1 ..];
                source = source[0..at];
            }
            if (eql(source, "herdr")) source = "Soul-Brews-Studio/maw-herdr-plugin";
            if (!std.mem.startsWith(u8, source, "https://")) {
                var pieces = std.mem.splitScalar(u8, source, '/');
                const owner = pieces.next() orelse return error.InvalidSource;
                const repo = pieces.next() orelse return error.InvalidSource;
                if (!safeName(owner) or !safeName(repo) or pieces.next() != null) return error.InvalidSource;
                source = try std.fmt.allocPrint(c.a, "https://github.com/{s}/{s}", .{ owner, repo });
            }
        }
        try std.Io.Dir.cwd().createDirPath(c.io, root);
        var random: [12]u8 = undefined;
        c.io.random(&random);
        const stage = try c.join(&.{ root, try std.fmt.allocPrint(c.a, ".maw-install-{x}", .{random}) });
        try std.Io.Dir.cwd().createDir(c.io, stage, .default_dir);
        defer std.Io.Dir.cwd().deleteTree(c.io, stage) catch {};
        _ = try c.git(cwd, &.{ "clone", "--no-checkout", "--no-local", "--", source, stage });
        const commit = if (ref) |r| try c.fetchRef(stage, r) else try c.git(stage, &.{ "rev-parse", "HEAD" });
        const m = try c.candidate(stage, commit);
        if (ref != null) {
            _ = try c.git(stage, &.{ "checkout", "--detach", commit });
        } else {
            _ = try c.git(stage, &.{"checkout"});
        }
        _ = try c.current(stage);
        const destination = try c.join(&.{ root, m.name });
        try c.publish(stage, destination);
        try c.out("installed {s}\ncommit {s}\n", .{ m.name, commit });
        return 0;
    }
    fn operate(c: Context, verb: []const u8, name: []const u8, ref: ?[]const u8) !u8 {
        const root = try inventory.pluginRoot(c.a, c.io, c.env);
        if (eql(verb, "install")) return c.install(root, name, ref);
        const dir = try c.checkout(root, name);
        const m = try c.current(dir);
        if (!eql(m.name, name)) return error.PluginNameMismatch;
        const dirty = (try c.git(dir, &.{ "status", "--porcelain", "--untracked-files=all" })).len != 0;
        if (eql(verb, "update")) {
            if (dirty) return error.DirtyCheckout;
            const branch = try c.git(dir, &.{ "rev-parse", "--abbrev-ref", "HEAD" });
            if (ref == null and eql(branch, "HEAD")) {
                try c.out("{s} is pinned at {s}\n", .{ name, try c.git(dir, &.{ "rev-parse", "HEAD" }) });
                return 0;
            }
            const commit = if (ref) |r| try c.fetchRef(dir, r) else blk: {
                _ = try c.git(dir, &.{ "fetch", "--no-recurse-submodules", "origin" });
                break :blk try c.git(dir, &.{ "rev-parse", "--verify", "@{upstream}^{commit}" });
            };
            if (!eql((try c.candidate(dir, commit)).name, name)) return error.PluginNameMismatch;
            if (ref != null) {
                _ = try c.git(dir, &.{ "checkout", "--detach", commit });
            } else {
                _ = try c.git(dir, &.{ "merge", "--ff-only", commit });
            }
            try c.out("updated {s}\ncommit {s}\n", .{ name, commit });
            return 0;
        }
        const hash = try c.git(dir, &.{ "hash-object", "--no-filters", "--", m.entry });
        const expected = c.git(dir, &.{ "rev-parse", try std.fmt.allocPrint(c.a, "HEAD:{s}", .{m.entry}) }) catch "";
        const modified = dirty or !eql(hash, expected);
        try c.out("source {s}\ncommit {s}\nentry {s}\nhash {s}\nstatus {s}\n", .{ try c.git(dir, &.{ "remote", "get-url", "origin" }), try c.git(dir, &.{ "rev-parse", "HEAD" }), m.entry, hash, if (modified) "modified" else "clean" });
        return if (eql(verb, "check") and modified) 1 else 0;
    }
};
pub fn run(a: std.mem.Allocator, io: std.Io, env: *const std.process.Environ.Map, args: []const []const u8, legacy: bool) !u8 {
    if (args.len == 0 or eql(args[0], "ls") or eql(args[0], "list") or std.mem.startsWith(u8, args[0], "-")) return inventory.run(a, io, env, args, legacy);
    const verb = args[0];
    const mutation = eql(verb, "install") or eql(verb, "update");
    if ((!mutation and !eql(verb, "info") and !eql(verb, "check")) or (args.len != 2 and !(mutation and args.len == 4 and eql(args[2], "--ref") and args[3].len > 0))) {
        try std.Io.File.stderr().writeStreamingAll(io, "maw: usage: maw plugin <ls|list|install|update|info|check> [args]\n");
        return 2;
    }
    const c = Context{ .a = a, .io = io, .env = env };
    return c.operate(verb, args[1], if (args.len == 4) args[3] else null) catch |err| {
        try std.Io.File.stderr().writeStreamingAll(io, try std.fmt.allocPrint(a, "maw: plugin {s}: {s}\n", .{ verb, @errorName(err) }));
        return 1;
    };
}
