use crate::plugins;
use std::collections::BTreeMap;
use std::ffi::OsString;
use std::path::PathBuf;

struct Command {
    summary: &'static str,
    usage: &'static str,
    path: Option<PathBuf>,
}

type Registry = BTreeMap<String, Command>;

fn fail(message: &str) -> i32 {
    eprintln!("maw: {}", message);
    2
}

fn unknown(name: &OsString) -> i32 {
    fail(&format!(
        "unknown command {:?}; run 'maw help'",
        name.to_string_lossy()
    ))
}

// Columns of the terminal on stdout; None when stdout is not a terminal. Plain
// libc ioctl: std has no terminal size, and no crate is approved for one.
#[cfg(any(
    target_os = "macos",
    all(
        target_os = "linux",
        any(target_arch = "x86_64", target_arch = "aarch64")
    )
))]
fn terminal_width() -> Option<usize> {
    use std::os::raw::{c_int, c_ulong};
    #[repr(C)]
    struct Size {
        _rows: u16,
        columns: u16,
        _x: u16,
        _y: u16,
    }
    extern "C" {
        fn ioctl(fd: c_int, request: c_ulong, ...) -> c_int;
    }
    #[cfg(target_os = "linux")]
    const TIOCGWINSZ: c_ulong = 0x5413;
    #[cfg(target_os = "macos")]
    const TIOCGWINSZ: c_ulong = 0x4008_7468;
    let mut size = Size {
        _rows: 0,
        columns: 0,
        _x: 0,
        _y: 0,
    };
    // Safety: TIOCGWINSZ writes exactly one winsize, which Size mirrors.
    let status = unsafe { ioctl(1, TIOCGWINSZ, &mut size as *mut Size) };
    if status == 0 && size.columns > 0 {
        Some(size.columns as usize)
    } else {
        None
    }
}

#[cfg(not(any(
    target_os = "macos",
    all(
        target_os = "linux",
        any(target_arch = "x86_64", target_arch = "aarch64")
    )
)))]
fn terminal_width() -> Option<usize> {
    None
}

// Aligns labels in one column and cuts each row to `columns` characters,
// ending a cut summary with an ellipsis.
fn print_rows(rows: &[(String, String)], columns: usize) {
    let width = rows
        .iter()
        .map(|(label, _)| label.len())
        .max()
        .unwrap_or(0)
        .max(12);
    for (label, summary) in rows {
        let head = format!("  {:width$}", label, width = width);
        let chars: Vec<char> = summary.chars().collect();
        let room = columns.saturating_sub(head.len() + 1);
        if !chars.is_empty() && chars.len() <= room {
            println!("{} {}", head, summary);
        } else if !chars.is_empty() && room > 0 {
            println!("{} {}…", head, chars[..room - 1].iter().collect::<String>());
        } else {
            println!("{}", head.trim_end());
        }
    }
}

// Built-ins, installed plugins and PATH executables as separate sections (#53).
// Installed plugins come from manifests only; nothing runs.
fn root_help(registry: &Registry) {
    let columns = terminal_width().unwrap_or(80);
    println!("Usage: maw <command> [args]\n\nCommands:");
    let mut external = Vec::new();
    for (name, command) in registry {
        if command.path.is_some() {
            external.push((name.clone(), format!("maw-{}", name)));
        } else if name != "plugins" {
            println!("  {:12} {}", name, command.summary);
        }
    }
    match crate::inventory::help_plugins() {
        Err(e) => eprintln!("maw: installed plugins not listed: {}\n  maw plugin ls", e),
        Ok((installed, disabled)) if !installed.is_empty() || disabled > 0 => {
            let rows: Vec<(String, String)> = installed
                .into_iter()
                .map(|p| {
                    let aliases: Vec<&str> = p
                        .aliases
                        .iter()
                        .map(String::as_str)
                        .filter(|alias| !registry.contains_key(*alias))
                        .collect();
                    let label = if aliases.is_empty() {
                        p.command.clone()
                    } else {
                        format!("{} ({})", p.command, aliases.join(", "))
                    };
                    let summary = match registry.get(&p.command) {
                        Some(shadow) => {
                            let mark = if shadow.path.is_some() {
                                format!("(shadowed by PATH maw-{})", p.command)
                            } else {
                                "(shadowed by built-in)".to_owned()
                            };
                            format!("{} {}", mark, p.summary).trim().to_owned()
                        }
                        None => p.summary,
                    };
                    (label, summary)
                })
                .collect();
            println!("\nInstalled plugins:");
            print_rows(&rows, columns);
            if disabled > 0 {
                println!("  {} disabled — maw plugin ls --all", disabled);
            }
        }
        Ok(_) => {}
    }
    if !external.is_empty() {
        println!("\nExternal (PATH):");
        print_rows(&external, columns);
    }
    println!("\nRun 'maw help <command>' for command help.\nPlugins: executable maw-<command> files in absolute PATH directories.");
}

fn help(registry: &Registry, args: &[OsString]) -> i32 {
    if args.is_empty() {
        root_help(registry);
        return 0;
    }
    if args.len() != 1 {
        return fail("usage: maw help [command]");
    }
    match args[0].to_str().and_then(|name| registry.get(name)) {
        Some(command) => match &command.path {
            Some(path) => plugins::execute(path, &[OsString::from("--help")]),
            None => {
                println!("Usage: {}\n\n{}", command.usage, command.summary);
                0
            }
        },
        None => {
            crate::inventory::execute(args[0].to_str().unwrap_or(""), &[OsString::from("--help")])
                .unwrap_or_else(|| unknown(&args[0]))
        }
    }
}

pub fn run(args: Vec<OsString>) -> i32 {
    let mut registry = Registry::new();
    for (name, summary, usage) in [
        ("help", "Show command help", "maw help [command]"),
        ("version", "Show maw version", "maw version"),
        (
            "marketplace",
            "List known plugin sources",
            "maw marketplace [ls|list]",
        ),
        (
            "plugin",
            "Manage installed plugins",
            "maw plugin ls|list|install|update|info|check [args]",
        ),
        (
            "plugins",
            "Alias for plugin ls",
            "maw plugins [ls] [-v|--verbose] [--all]",
        ),
    ] {
        registry.insert(
            name.to_owned(),
            Command {
                summary,
                usage,
                path: None,
            },
        );
    }
    for (name, path) in plugins::discover() {
        registry.entry(name).or_insert(Command {
            summary: "External plugin",
            usage: "",
            path: Some(path),
        });
    }
    if args.is_empty() {
        return help(&registry, &[]);
    }
    let name = args[0].to_str().unwrap_or("");
    if matches!(name, "-h" | "--help" | "-v" | "--version") && args.len() != 1 {
        return fail("global help/version flags do not accept arguments");
    }
    let name = match name {
        "-h" | "--help" => "help",
        "-v" | "--version" => "version",
        name => name,
    };
    let command = match registry.get(name) {
        Some(command) => command,
        None => {
            return crate::inventory::execute(name, &args[1..]).unwrap_or_else(|| unknown(&args[0]))
        }
    };
    if let Some(path) = &command.path {
        return plugins::execute(path, &args[1..]);
    }
    if args.len() == 2 && (args[1] == "-h" || args[1] == "--help") {
        return help(&registry, &[OsString::from(name)]);
    }
    if name == "help" {
        return help(&registry, &args[1..]);
    }
    if name == "plugin" || name == "plugins" {
        if let Some(code) = crate::lifecycle::run(&args[1..]) {
            return code;
        }
        return crate::inventory::run(&args[1..], name == "plugins");
    }
    if name == "marketplace" {
        return crate::lifecycle::marketplace(&args[1..]);
    }
    if args.len() != 1 {
        return fail(&format!("usage: {}", command.usage));
    }
    println!("maw {}", option_env!("MAW_VERSION").unwrap_or("dev"));
    0
}
