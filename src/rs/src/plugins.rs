use std::collections::BTreeMap;
use std::ffi::OsString;
use std::path::PathBuf;
use std::process::Command;

pub fn discover() -> BTreeMap<String, PathBuf> {
    let mut plugins = BTreeMap::new();
    let path = std::env::var_os("PATH").unwrap_or_default();
    for dir in std::env::split_paths(&path).filter(|dir| dir.is_absolute()) {
        let entries = match std::fs::read_dir(dir) {
            Ok(entries) => entries,
            Err(_) => continue,
        };
        for entry in entries.flatten() {
            let filename = entry.file_name();
            let filename = match filename.to_str() {
                Some(name) => name,
                None => continue,
            };
            #[cfg(windows)]
            let filename = match filename.strip_suffix(".exe") {
                Some(name) => name,
                None => continue,
            };
            let name = match filename.strip_prefix("maw-") {
                Some(name) => name,
                None => continue,
            };
            if !valid_name(name)
                || matches!(name, "go" | "rs" | "js" | "zig")
                || plugins.contains_key(name)
            {
                continue;
            }
            let path = match std::fs::canonicalize(entry.path()) {
                Ok(path) => path,
                Err(_) => continue,
            };
            let metadata = match path.metadata() {
                Ok(metadata) if metadata.is_file() => metadata,
                _ => continue,
            };
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                if metadata.permissions().mode() & 0o111 == 0 {
                    continue;
                }
            }
            #[cfg(not(unix))]
            let _ = metadata;
            plugins.insert(name.to_owned(), path);
        }
    }
    plugins
}

fn valid_name(name: &str) -> bool {
    name.as_bytes()
        .first()
        .map_or(false, u8::is_ascii_lowercase)
        && name
            .bytes()
            .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'-')
}

pub fn execute(path: &PathBuf, args: &[OsString]) -> i32 {
    match Command::new(path).args(args).status() {
        Ok(status) => status.code().unwrap_or(126),
        Err(error) => {
            eprintln!("maw: cannot execute {}: {}", path.display(), error);
            126
        }
    }
}
