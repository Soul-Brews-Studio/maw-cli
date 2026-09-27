use serde_json::{Map, Value};
use std::collections::BTreeSet;
use std::ffi::OsString;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::{Duration, Instant};

type Object = Map<String, Value>;
type Result<T> = std::result::Result<T, String>;
const MAX: u64 = 1048576;
struct Plugin {
    name: String,
    version: String,
    tier: usize,
    dir: PathBuf,
    enabled: bool,
    cli: bool,
    api: bool,
    missing: bool,
    command: String,
    runtime: String,
    target: String,
    interactive: bool,
    entry: Option<PathBuf>,
}
const TIERS: [&str; 3] = ["core", "standard", "extra"];

fn safe(value: &str) -> String {
    let mut out = String::new();
    for c in value.chars() {
        if (c as u32) < 32 || (127..=159).contains(&(c as u32)) {
            out.push_str(&format!("\\u{:04x}", c as u32));
        } else {
            out.push(c);
        }
    }
    out
}
fn display(path: &Path) -> String {
    safe(&path.to_string_lossy())
}
fn text<'a>(object: &'a Object, key: &str) -> &'a str {
    object.get(key).and_then(Value::as_str).unwrap_or("")
}
fn weight(value: Option<&Value>) -> Option<f64> {
    value
        .and_then(Value::as_f64)
        .filter(|n| n.is_finite() && *n >= 0.0 && *n <= 99.0)
}
fn read_json(path: &Path) -> Result<Option<Object>> {
    let error = || format!("cannot read JSON metadata: {}", display(path));
    let stat = match fs::metadata(path) {
        Ok(s) => s,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err(error()),
    };
    if !stat.is_file() || stat.len() > MAX {
        return Err(error());
    }
    let mut bytes = Vec::new();
    let file = fs::File::open(path).map_err(|_| error())?;
    let opened = file.metadata().map_err(|_| error())?;
    if !opened.is_file() || opened.len() > MAX {
        return Err(error());
    }
    file.take(MAX + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| error())?;
    if bytes.len() as u64 > MAX {
        return Err(error());
    }
    let source = std::str::from_utf8(&bytes).map_err(|_| error())?;
    match serde_json::from_str::<Value>(source).map_err(|_| error())? {
        Value::Object(m) => Ok(Some(m)),
        _ => Err(error()),
    }
}
fn directories(root: &Path) -> Result<Vec<PathBuf>> {
    let entries = match fs::read_dir(root) {
        Ok(e) => e,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(_) => return Err(format!("cannot read directory: {}", display(root))),
    };
    let mut paths = Vec::new();
    for e in entries {
        paths.push(
            e.map_err(|_| format!("cannot read directory: {}", display(root)))?
                .path(),
        );
    }
    paths.sort();
    Ok(paths)
}
fn env(key: &str) -> Option<PathBuf> {
    std::env::var_os(key)
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
}
fn absolute(path: PathBuf) -> Result<PathBuf> {
    use std::path::Component;
    let path = if path.is_absolute() {
        path
    } else {
        std::env::current_dir()
            .map_err(|e| e.to_string())?
            .join(path)
    };
    let mut normalized = PathBuf::new();
    for component in path.components() {
        match component {
            Component::ParentDir => {
                normalized.pop();
            }
            Component::CurDir => {}
            _ => normalized.push(component.as_os_str()),
        }
    }
    Ok(normalized)
}
pub(crate) fn paths() -> Result<(PathBuf, PathBuf)> {
    let home = env("HOME")
        .or_else(|| env("USERPROFILE"))
        .unwrap_or_default();
    let xdg = matches!(
        std::env::var("MAW_XDG")
            .unwrap_or_default()
            .to_lowercase()
            .as_str(),
        "1" | "true" | "yes" | "on"
    );
    if home.as_os_str().is_empty()
        && ((env("MAW_PLUGINS_DIR").is_none()
            && env("MAW_HOME").is_none()
            && env("MAW_DATA_DIR").is_none()
            && !(xdg && env("XDG_DATA_HOME").is_some()))
            || (env("MAW_HOME").is_none()
                && env("MAW_CONFIG_DIR").is_none()
                && env("XDG_CONFIG_HOME").is_none()))
    {
        return Err("HOME is not set; provide explicit plugin and config roots".into());
    }
    let data = env("MAW_HOME")
        .or_else(|| env("MAW_DATA_DIR"))
        .unwrap_or_else(|| {
            if xdg {
                env("XDG_DATA_HOME")
                    .unwrap_or_else(|| home.join(".local/share"))
                    .join("maw")
            } else {
                home.join(".maw")
            }
        });
    let plugins = env("MAW_PLUGINS_DIR").unwrap_or_else(|| data.join("plugins"));
    let config = env("MAW_HOME")
        .map(|p| p.join("config"))
        .or_else(|| env("MAW_CONFIG_DIR"))
        .unwrap_or_else(|| {
            env("XDG_CONFIG_HOME")
                .unwrap_or_else(|| home.join(".config"))
                .join("maw")
        });
    Ok((absolute(plugins)?, absolute(config)?))
}
fn disabled_plugins(root: &Path) -> Result<BTreeSet<String>> {
    let mut files = Vec::new();
    for path in directories(root)? {
        let name = path.file_name().and_then(|s| s.to_str()).unwrap_or("");
        if let Some(middle) = name
            .strip_prefix("maw.config.")
            .and_then(|s| s.strip_suffix(".json"))
        {
            let local = middle.ends_with(".local");
            let number = middle.strip_suffix(".local").unwrap_or(middle);
            if !number.is_empty() && number.bytes().all(|b| b.is_ascii_digit()) {
                files.push((number.trim_start_matches('0').to_string(), local, path));
            }
        }
    }
    files.sort_by(|a, b| {
        a.0.len()
            .cmp(&b.0.len())
            .then_with(|| a.0.cmp(&b.0))
            .then_with(|| a.1.cmp(&b.1))
            .then_with(|| a.2.cmp(&b.2))
    });
    if files.is_empty() {
        files.push((String::new(), false, root.join("maw.config.json")));
    }
    let mut disabled = BTreeSet::new();
    for (_, _, path) in files {
        if let Some(m) = read_json(&path)? {
            if let Some(values) = m.get("disabledPlugins").and_then(Value::as_array) {
                disabled = values
                    .iter()
                    .filter_map(Value::as_str)
                    .map(str::to_owned)
                    .collect();
            }
        }
    }
    Ok(disabled)
}
fn manifest(
    m: &Object,
    dir: PathBuf,
    overrides: &Object,
    disabled: &BTreeSet<String>,
) -> Option<Plugin> {
    let name = text(m, "name");
    let version = text(m, "version");
    if name.is_empty()
        || !name
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b"._-".contains(&c))
        || version.is_empty()
        || safe(version) != version
    {
        return None;
    }
    if m.contains_key("tier") && !TIERS.contains(&text(m, "tier")) {
        return None;
    }
    if m.contains_key("weight") && weight(m.get("weight")).is_none() {
        return None;
    }
    let w = weight(overrides.get(name))
        .or_else(|| weight(m.get("weight")))
        .unwrap_or(50.0);
    let tier = TIERS
        .iter()
        .position(|t| *t == text(m, "tier"))
        .unwrap_or(if w < 10.0 {
            0
        } else if w < 50.0 {
            1
        } else {
            2
        });
    let mut entry = text(m, "entry");
    if entry.is_empty() && text(m, "target") != "wasm" {
        entry = m
            .get("artifact")
            .and_then(Value::as_object)
            .map(|a| text(a, "path"))
            .unwrap_or("");
    }
    if entry.is_empty() {
        entry = text(m, "wasm");
    }
    let cli = m.get("cli").map_or(false, Value::is_object) || !entry.is_empty();
    let api = m.get("api").map_or(false, Value::is_object);
    let missing = if entry.is_empty() {
        cli
    } else {
        !absolute(dir.join(entry)).ok()?.is_file()
    };
    let cli_metadata = m.get("cli").and_then(Value::as_object);
    let command = cli_metadata
        .map(|cli| {
            let command = text(cli, "command");
            if command.is_empty() {
                name
            } else {
                command
            }
        })
        .unwrap_or("");
    let entry = if entry.is_empty() {
        None
    } else {
        Some(absolute(dir.join(entry)).ok()?)
    };
    Some(Plugin {
        name: name.to_string(),
        version: version.to_string(),
        tier,
        dir,
        enabled: !disabled.contains(name),
        cli,
        api,
        missing,
        command: command.to_owned(),
        runtime: text(m, "runtime").to_owned(),
        target: text(m, "target").to_owned(),
        interactive: cli_metadata
            .and_then(|cli| cli.get("interactive"))
            .and_then(Value::as_bool)
            .unwrap_or(false),
        entry,
    })
}
fn scan(root: &Path, disabled: &BTreeSet<String>) -> Result<Vec<Plugin>> {
    let overrides = read_json(&root.join(".overrides.json"))?.unwrap_or_default();
    let mut found = BTreeSet::new();
    let mut plugins = Vec::new();
    for dir in directories(root)? {
        if !dir.is_dir() {
            continue;
        }
        match read_json(&dir.join("plugin.json")) {
            Ok(None) => {
                if dir.join("plugin.ts").exists() {
                    eprintln!("maw: skipped TypeScript-only manifest: {}", display(&dir));
                }
            }
            result => {
                let parsed = result
                    .ok()
                    .flatten()
                    .and_then(|m| manifest(&m, dir.clone(), &overrides, disabled));
                if let Some(p) = parsed {
                    if found.insert(p.name.clone()) {
                        plugins.push(p);
                    }
                } else {
                    eprintln!("maw: skipped invalid plugin.json: {}", display(&dir));
                }
            }
        }
    }
    plugins.sort_by(|a, b| a.tier.cmp(&b.tier).then_with(|| a.name.cmp(&b.name)));
    Ok(plugins)
}
fn render(plugins: &[Plugin], verbose: bool, all: bool) {
    if plugins.is_empty() {
        println!("no plugins installed");
        return;
    }
    let active = plugins.iter().filter(|p| p.enabled).count();
    let disabled = plugins.len() - active;
    let visible: Vec<_> = plugins.iter().filter(|p| all || p.enabled).collect();
    if verbose {
        for p in visible {
            println!(
                "{}\t{}\t{}\t{}\t{}",
                p.name,
                p.version,
                TIERS[p.tier],
                if p.enabled { "enabled" } else { "disabled" },
                display(&p.dir)
            );
        }
        return;
    }
    let mut tiers = [0; 3];
    for p in &visible {
        tiers[p.tier] += 1;
    }
    let missing = visible.iter().filter(|p| p.missing).count();
    let health = if missing == 0 {
        "ok".to_string()
    } else {
        format!(
            "{} missing executable{}",
            missing,
            if missing == 1 { "" } else { "s" }
        )
    };
    println!(
        "{} plugin{} ({} active, {} disabled)",
        plugins.len(),
        if plugins.len() == 1 { "" } else { "s" },
        active,
        disabled
    );
    println!(
        "  core: {} · standard: {} · extra: {}",
        tiers[0], tiers[1], tiers[2]
    );
    println!(
        "  cli: {} · api: {} · health: {}",
        visible.iter().filter(|p| p.cli).count(),
        visible.iter().filter(|p| p.api).count(),
        health
    );
    if !visible.is_empty() {
        println!(
            "  {}",
            visible
                .iter()
                .map(|p| p.name.as_str())
                .collect::<Vec<_>>()
                .join(" · ")
        );
    }
    if !all && disabled > 0 {
        println!("  disabled hidden by default — use --all to include");
    }
}

pub fn run(args: &[OsString], legacy: bool) -> i32 {
    let usage = format!(
        "maw: usage: maw {} [-v|--verbose] [--all]",
        if legacy { "plugins [ls]" } else { "plugin ls" }
    );
    let flags = if args.first().map_or(false, |s| s == "ls" || s == "list") {
        &args[1..]
    } else if legacy {
        args
    } else {
        eprintln!("{}", usage);
        return 2;
    };
    let (mut verbose, mut all) = (false, false);
    for flag in flags {
        if (flag == "-v" || flag == "--verbose") && !verbose {
            verbose = true;
        } else if flag == "--all" && !all {
            all = true;
        } else {
            eprintln!("{}", usage);
            return 2;
        }
    }
    let result = paths().and_then(|(root, config)| {
        disabled_plugins(&config).and_then(|disabled| scan(&root, &disabled))
    });
    match result {
        Ok(plugins) => {
            render(&plugins, verbose, all);
            0
        }
        Err(e) => {
            eprintln!("maw: {}", e);
            1
        }
    }
}

// The short commit of a plugin directory that is its own Git checkout, for
// `maw <plugin> version` (#52); None for anything else. `--show-prefix` prints
// an empty line only at the top of a work tree, so an enclosing repository never
// answers for a plugin inside it. Inherited GIT_* routing (a hook's GIT_DIR) is
// dropped, GIT_OPTIONAL_LOCKS=0 keeps it from writing, and any failure or the
// two-second timeout reads as "not a Git checkout".
fn short_commit(dir: &Path) -> Option<String> {
    let mut cmd = std::process::Command::new("git");
    for (key, _) in std::env::vars_os() {
        if key.to_string_lossy().starts_with("GIT_") {
            cmd.env_remove(key);
        }
    }
    let mut child = cmd
        .env("GIT_OPTIONAL_LOCKS", "0")
        .arg("-C")
        .arg(dir)
        .args(["rev-parse", "--show-prefix", "--short", "HEAD"])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .ok()?;
    let deadline = Instant::now() + Duration::from_secs(2);
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status,
            Ok(None) if Instant::now() < deadline => std::thread::sleep(Duration::from_millis(5)),
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                return None;
            }
        }
    };
    let mut out = String::new();
    child.stdout.take()?.read_to_string(&mut out).ok()?;
    let hash = out.strip_prefix('\n')?;
    let hash = hash.strip_suffix('\n').unwrap_or(hash);
    let valid = status.success()
        && (4..=64).contains(&hash.len())
        && hash.bytes().all(|c| matches!(c, b'0'..=b'9' | b'a'..=b'f'));
    if valid {
        Some(hash.to_owned())
    } else {
        None
    }
}

// Called only after builtin and PATH command lookup has failed.
pub fn execute(name: &str, args: &[OsString]) -> Option<i32> {
    if !name
        .as_bytes()
        .first()
        .map_or(false, u8::is_ascii_lowercase)
        || !name
            .bytes()
            .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'-')
        || matches!(name, "go" | "rs" | "js" | "zig" | "index")
    {
        return None;
    }
    let inventory = paths().and_then(|(root, config)| {
        disabled_plugins(&config).and_then(|disabled| scan(&root, &disabled))
    });
    let inventory = match inventory {
        Ok(plugins) => plugins,
        Err(e) => {
            eprintln!("maw: {}", e);
            return Some(1);
        }
    };
    let plugin = inventory.into_iter().find(|p| p.command == name)?;
    let fail = |code, reason| {
        eprintln!("maw: plugin {} {}", plugin.name, reason);
        Some(code)
    };
    if !plugin.enabled {
        return fail(1, "is disabled");
    }
    // Reserved verb (#52): the host answers from plugin.json; no plugin code runs.
    if args.len() == 1 && (args[0] == "version" || args[0] == "--version") {
        let commit = short_commit(&plugin.dir);
        let commit = commit.as_deref().unwrap_or("not a Git checkout");
        println!("{} {} ({})", plugin.name, plugin.version, commit);
        return Some(0);
    }
    if plugin.runtime != "bun-dev" || plugin.target != "js" || !plugin.interactive {
        return fail(126, "is not a standalone Bun CLI (requires runtime=bun-dev, target=js, cli.interactive=true)");
    }
    let entry = match plugin.entry.as_ref().filter(|path| path.is_file()) {
        Some(entry) => entry,
        None => return fail(126, "entry is missing or not a regular file"),
    };
    let path = std::env::var_os("PATH").unwrap_or_default();
    let bun = std::env::split_paths(&path)
        .filter(|dir| dir.is_absolute())
        .map(|dir| dir.join(if cfg!(windows) { "bun.exe" } else { "bun" }))
        .find(|path| {
            let metadata = match path.metadata() {
                Ok(m) if m.is_file() => m,
                _ => return false,
            };
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                metadata.permissions().mode() & 0o111 != 0
            }
            #[cfg(not(unix))]
            {
                let _ = metadata;
                true
            }
        });
    let bun = match bun {
        Some(bun) => bun,
        None => return fail(126, "requires bun on PATH"),
    };
    match std::process::Command::new(&bun)
        .arg(entry)
        .args(args)
        .status()
    {
        Ok(status) => Some(status.code().unwrap_or(126)),
        Err(error) => fail(
            126,
            &format!("cannot execute bun {}: {}", display(&bun), error),
        ),
    }
}
