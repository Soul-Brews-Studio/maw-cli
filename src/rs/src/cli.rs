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

fn help(registry: &Registry, args: &[OsString]) -> i32 {
    if args.is_empty() {
        println!("Usage: maw <command> [args]\n\nCommands:");
        for (name, command) in registry {
            println!("  {:12} {}", name, command.summary);
        }
        println!("\nRun 'maw help <command>' for command help.\nPlugins: executable maw-<command> files in absolute PATH directories.");
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
        None => unknown(&args[0]),
    }
}

pub fn run(args: Vec<OsString>) -> i32 {
    let mut registry = Registry::new();
    for (name, summary, usage) in [
        ("help", "Show command help", "maw help [command]"),
        ("version", "Show maw version", "maw version"),
        (
            "plugin",
            "List commands and executable plugin paths",
            "maw plugin ls",
        ),
        ("plugins", "Alias for plugin ls", "maw plugins [ls]"),
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
        None => return unknown(&args[0]),
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
    let valid_args = if name == "plugin" || name == "plugins" {
        (args.len() == 2 && args[1] == "ls") || (name == "plugins" && args.len() == 1)
    } else {
        args.len() == 1
    };
    if !valid_args {
        return fail(&format!("usage: {}", command.usage));
    }
    if name == "version" {
        println!("maw {}", option_env!("MAW_VERSION").unwrap_or("dev"));
    } else {
        println!("NAME\tTYPE\tPATH");
        for (name, command) in &registry {
            match &command.path {
                Some(path) => println!("{}\texternal\t{}", name, path.display()),
                None => println!("{}\tbuiltin\t-", name),
            }
        }
    }
    0
}
