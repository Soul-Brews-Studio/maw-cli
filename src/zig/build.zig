const std = @import("std");

pub fn build(b: *std.Build) void {
    const exe = b.addExecutable(.{
        .name = "maw-zig",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = b.standardTargetOptions(.{}),
            .optimize = b.standardOptimizeOption(.{}),
        }),
    });
    const options = b.addOptions();
    options.addOption([]const u8, "version", b.option([]const u8, "version", "Release version") orelse "dev");
    exe.root_module.addOptions("build_options", options);
    b.installArtifact(exe);
}
