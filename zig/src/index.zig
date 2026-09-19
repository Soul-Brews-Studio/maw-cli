const std = @import("std");

const max_input = 64 * 1024 * 1024;
const Postings = std.StringHashMap(std.ArrayList(usize));

fn field(value: std.json.Value, name: []const u8) !std.json.Value {
    if (value != .object) return error.InvalidSchema;
    return value.object.get(name) orelse error.InvalidSchema;
}

fn string(value: std.json.Value) ![]const u8 {
    if (value != .string) return error.InvalidSchema;
    return value.string;
}

fn tokenByte(c: u8) bool {
    return (c >= 'a' and c <= 'z') or (c >= 'A' and c <= 'Z') or (c >= '0' and c <= '9') or c == '_';
}

fn lessThan(_: void, a: []const u8, b: []const u8) bool {
    return std.mem.lessThan(u8, a, b);
}

fn hashBytes(hash: *u64, bytes: []const u8) void {
    for (bytes) |byte| hash.* = (hash.* ^ byte) *% 1099511628211;
}

// The bounded prototype buffers the full input and retains real postings lists.
// Parsed record trees are freed after each line; retained keys own their bytes.
pub fn run(allocator: std.mem.Allocator, io: std.Io, path: []const u8) !void {
    const stdin = std.mem.eql(u8, path, "-");
    const file = if (stdin) std.Io.File.stdin() else try std.Io.Dir.cwd().openFile(io, path, .{});
    defer if (!stdin) file.close(io);
    var buffer: [64 * 1024]u8 = undefined;
    var reader = file.readerStreaming(io, &buffer);
    const input = try reader.interface.allocRemaining(allocator, .limited(max_input + 1));
    defer allocator.free(input);
    if (input.len > max_input) return error.StreamTooLong;
    if (!std.unicode.utf8ValidateSlice(input)) return error.InvalidUtf8;

    var postings = Postings.init(allocator);
    var symbols = std.StringHashMap(void).init(allocator);
    var records: usize = 0;
    var text_bytes: usize = 0;
    var posting_count: usize = 0;
    var token: std.ArrayList(u8) = .empty;
    var record_arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer record_arena.deinit();
    var lines = std.mem.splitScalar(u8, input, '\n');
    while (lines.next()) |raw_line| {
        const line = std.mem.trim(u8, raw_line, " \t\r");
        if (line.len == 0) continue;
        const parsed = try std.json.parseFromSliceLeaky(std.json.Value, record_arena.allocator(), line, .{ .duplicate_field_behavior = .use_last });
        defer _ = record_arena.reset(.retain_capacity);
        if (!std.mem.eql(u8, try string(try field(parsed, "jsonrpc")), "2.0")) return error.InvalidSchema;
        const structured = try field(try field(parsed, "result"), "structuredContent");
        const source = try string(try field(structured, "file"));
        const symbol = try string(try field(structured, "symbol"));
        const text = try string(try field(structured, "text"));
        if (source.len == 0 or symbol.len == 0 or std.mem.indexOfScalar(u8, source, 0) != null or std.mem.indexOfScalar(u8, symbol, 0) != null) return error.InvalidSchema;
        const symbol_key = try std.fmt.allocPrint(allocator, "{s}\x00{s}", .{ source, symbol });
        const unique = try symbols.getOrPut(symbol_key);
        if (unique.found_existing) allocator.free(symbol_key);
        text_bytes += text.len;

        var position: usize = 0;
        while (position < text.len) {
            while (position < text.len and !tokenByte(text[position])) : (position += 1) {}
            token.clearRetainingCapacity();
            while (position < text.len and tokenByte(text[position])) : (position += 1) {
                try token.append(allocator, std.ascii.toLower(text[position]));
            }
            if (token.items.len == 0) continue;
            if (postings.getPtr(token.items)) |list| {
                if (list.items[list.items.len - 1] == records) continue;
                try list.append(allocator, records);
            } else {
                const key = try allocator.dupe(u8, token.items);
                var list: std.ArrayList(usize) = .empty;
                try list.append(allocator, records);
                try postings.put(key, list);
            }
            posting_count += 1;
        }
        records += 1;
    }

    var terms: std.ArrayList([]const u8) = .empty;
    var keys = postings.keyIterator();
    while (keys.next()) |key| try terms.append(allocator, key.*);
    std.mem.sort([]const u8, terms.items, {}, lessThan);
    var hash: u64 = 14695981039346656037;
    for (terms.items) |term| {
        hashBytes(&hash, term);
        hashBytes(&hash, ":");
        var count_buffer: [32]u8 = undefined;
        const count = try std.fmt.bufPrint(&count_buffer, "{d}\n", .{postings.get(term).?.items.len});
        hashBytes(&hash, count);
    }
    const summary = try std.fmt.allocPrint(allocator, "{{\"records\":{d},\"input_bytes\":{d},\"text_bytes\":{d},\"unique_symbols\":{d},\"unique_terms\":{d},\"postings\":{d},\"checksum\":\"{x:0>16}\"}}\n", .{ records, input.len, text_bytes, symbols.count(), postings.count(), posting_count, hash });
    try std.Io.File.stdout().writeStreamingAll(io, summary);
}
