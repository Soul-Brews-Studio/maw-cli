use serde_json::Value;
use std::{
    ffi::OsString,
    fs,
    path::{Path, PathBuf},
    process::Command,
};
type Result<T> = std::result::Result<T, String>;
const HERDR: &str = "https://github.com/Soul-Brews-Studio/maw-herdr-plugin";
const MAX: usize = 1048576;

fn git(dir: &Path, args: &[&str]) -> Result<String> {
    let mut cmd = Command::new("git");
    for (key, _) in std::env::vars_os() {
        if key.to_string_lossy().starts_with("GIT_") {
            cmd.env_remove(key);
        }
    }
    let output = cmd
        .current_dir(dir)
        .env("GIT_CONFIG_GLOBAL", "/dev/null")
        .env("GIT_CONFIG_SYSTEM", "/dev/null")
        .env("GIT_CONFIG_NOSYSTEM", "1")
        .env("GIT_TERMINAL_PROMPT", "0")
        .env("GIT_LFS_SKIP_SMUDGE", "1")
        .args([
            "--literal-pathspecs",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "user.name=maw",
            "-c",
            "user.email=maw@localhost",
            "-c",
            "protocol.ext.allow=never",
        ])
        .args(args)
        .output()
        .map_err(|e| format!("cannot execute git: {e}"))?;
    if !output.status.success() {
        return Err(format!(
            "git {} failed: {}",
            args[0],
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    String::from_utf8(output.stdout).map_err(|_| "Git output is not UTF-8".into())
}
fn safe_name(name: &str) -> bool {
    name.as_bytes()
        .first()
        .map_or(false, u8::is_ascii_alphanumeric)
        && name
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"._-".contains(&b))
}
fn field<'a>(v: &'a Value, key: &str) -> &'a str {
    v.get(key).and_then(Value::as_str).unwrap_or("")
}
fn entry_path(entry: &str) -> bool {
    !entry.is_empty()
        && !entry.starts_with('/')
        && !entry.contains('\\')
        && !entry.chars().any(char::is_control)
        && entry
            .split('/')
            .all(|c| !c.is_empty() && c != "." && c != "..")
}
fn metadata(bytes: &[u8]) -> Result<(String, String)> {
    if bytes.len() > MAX {
        return Err("plugin.json exceeds 1 MiB".into());
    }
    let v: Value = serde_json::from_slice(bytes).map_err(|_| "invalid plugin.json")?;
    let name = field(&v, "name");
    let version = field(&v, "version");
    if !v.is_object()
        || !safe_name(name)
        || version.trim().is_empty()
        || version.chars().any(char::is_control)
    {
        return Err("invalid plugin name/version".into());
    }
    let mut entry = field(&v, "entry");
    if entry.is_empty() {
        entry = v.get("artifact").map(|a| field(a, "path")).unwrap_or("");
    }
    if entry.is_empty() {
        entry = field(&v, "wasm");
    }
    if !entry_path(entry) {
        return Err("unsafe plugin entry".into());
    }
    Ok((name.into(), entry.into()))
}
fn regular(dir: &Path, entry: &str) -> Result<PathBuf> {
    let mut path = dir.to_path_buf();
    let components: Vec<_> = entry.split('/').collect();
    for (i, c) in components.iter().enumerate() {
        path.push(c);
        let stat = fs::symlink_metadata(&path).map_err(|_| "missing plugin file")?;
        if stat.file_type().is_symlink()
            || (i + 1 == components.len() && !stat.is_file())
            || (i + 1 < components.len() && !stat.is_dir())
        {
            return Err("plugin path must be regular and in-tree".into());
        }
    }
    Ok(path)
}
fn tree_blob(dir: &Path, commit: &str, path: &str) -> Result<String> {
    let tree = git(dir, &["ls-tree", "-z", commit, "--", path])?;
    let mut entries = tree.split('\0').filter(|s| !s.is_empty());
    let row = entries.next().ok_or("entry not committed")?;
    if entries.next().is_some() {
        return Err("ambiguous entry".into());
    }
    let (head, name) = row.split_once('\t').ok_or("invalid Git tree")?;
    let parts: Vec<_> = head.split_whitespace().collect();
    if name != path
        || parts.len() != 3
        || !matches!(parts[0], "100644" | "100755")
        || parts[1] != "blob"
    {
        return Err("entry must be a committed regular file".into());
    }
    Ok(parts[2].into())
}
fn candidate(dir: &Path, commit: &str) -> Result<(String, String)> {
    let hash = tree_blob(dir, commit, "plugin.json")?;
    let size = git(dir, &["cat-file", "-s", &hash])?
        .trim()
        .parse::<usize>()
        .map_err(|_| "invalid blob size")?;
    if size > MAX {
        return Err("plugin.json exceeds 1 MiB".into());
    }
    let json = git(dir, &["show", &format!("{commit}:plugin.json")])?;
    let (name, entry) = metadata(json.as_bytes())?;
    tree_blob(dir, commit, &entry)?;
    Ok((name, entry))
}
fn installed(name: &str) -> Result<PathBuf> {
    if !safe_name(name) {
        return Err("unsafe plugin name".into());
    }
    let dir = crate::inventory::paths()?.0.join(name);
    let stat = fs::symlink_metadata(&dir).map_err(|_| "plugin is not installed")?;
    if !stat.is_dir() || stat.file_type().is_symlink() {
        return Err("plugin must be a real directory".into());
    }
    let git_dir = fs::symlink_metadata(dir.join(".git"))
        .map_err(|_| "plugin must have its own Git directory")?;
    if !git_dir.is_dir() || git_dir.file_type().is_symlink() {
        return Err("plugin must have its own real Git directory".into());
    }
    let top = git(&dir, &["rev-parse", "--show-toplevel"])?;
    if fs::canonicalize(top.trim()).ok() != fs::canonicalize(&dir).ok() {
        return Err("plugin must have its own Git checkout".into());
    }
    Ok(dir)
}
fn work_manifest(dir: &Path) -> Result<(String, String)> {
    let path = regular(dir, "plugin.json")?;
    if fs::metadata(&path).map_err(|e| e.to_string())?.len() > MAX as u64 {
        return Err("plugin.json exceeds 1 MiB".into());
    }
    let result = metadata(&fs::read(path).map_err(|e| e.to_string())?)?;
    regular(dir, &result.1)?;
    Ok(result)
}
fn resolve(dir: &Path, reference: &str) -> Result<String> {
    if reference.is_empty() || reference.starts_with('-') || reference.chars().any(char::is_control)
    {
        return Err("invalid ref".into());
    }
    if reference.starts_with('+') || reference.contains(':') {
        return Err("invalid ref".into());
    }
    git(dir, &["check-ref-format", "--allow-onelevel", reference])?;
    git(dir, &["fetch", "--no-tags", "origin", reference])?;
    let sha = git(dir, &["rev-parse", "--verify", "FETCH_HEAD^{commit}"])?
        .trim()
        .to_owned();
    if reference.len() == 40
        && reference.bytes().all(|b| b.is_ascii_hexdigit())
        && !sha.eq_ignore_ascii_case(reference)
    {
        return Err("resolved commit does not match requested SHA".into());
    }
    Ok(sha)
}
fn source(input: &str) -> Result<(String, Option<String>)> {
    if Path::new(input).is_dir() {
        return Ok((
            fs::canonicalize(input)
                .map_err(|e| e.to_string())?
                .to_string_lossy()
                .into(),
            None,
        ));
    }
    let (value, reference) = input
        .rsplit_once('@')
        .map(|(a, b)| (a, Some(b.to_owned())))
        .unwrap_or((input, None));
    if value == "herdr" {
        return Ok((HERDR.into(), reference));
    }
    if value.starts_with("https://") && value.len() > 8 && !value.chars().any(char::is_whitespace) {
        return Ok((value.into(), reference));
    }
    let parts: Vec<_> = value.split('/').collect();
    if parts.len() == 2 && parts.iter().all(|s| safe_name(s)) {
        return Ok((format!("https://github.com/{value}"), reference));
    }
    Err("source must be herdr, owner/repo, HTTPS URL, or local Git directory".into())
}
fn install(input: &str, reference: Option<&str>) -> Result<()> {
    let (source, shortref) = source(input)?;
    if reference.is_some() && shortref.is_some() {
        return Err("ref supplied twice".into());
    }
    let reference = reference.or(shortref.as_deref());
    let root = crate::inventory::paths()?.0;
    fs::create_dir_all(&root).map_err(|e| e.to_string())?;
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_nanos();
    let temp = root.join(format!(".maw-install-{}-{stamp}", std::process::id()));
    fs::create_dir(&temp).map_err(|e| e.to_string())?;
    let result = (|| {
        git(
            &root,
            &[
                "clone",
                "--no-checkout",
                "--no-local",
                "--template=",
                "--",
                &source,
                temp.to_str().ok_or("invalid path")?,
            ],
        )?;
        let commit = if let Some(reference) = reference {
            resolve(&temp, reference)?
        } else {
            git(&temp, &["rev-parse", "HEAD"])?.trim().into()
        };
        let (name, _) = candidate(&temp, &commit)?;
        let dest = root.join(&name);
        if fs::symlink_metadata(&dest).is_ok() {
            return Err("plugin destination already exists".into());
        }
        if reference.is_some() {
            git(&temp, &["checkout", "--detach", &commit, "--"])?;
        } else {
            git(&temp, &["checkout", "HEAD", "--"])?;
        }
        work_manifest(&temp)?;
        fs::rename(&temp, &dest).map_err(|e| e.to_string())?;
        println!("installed {name} {commit}");
        Ok(())
    })();
    if temp.exists() {
        let _ = fs::remove_dir_all(&temp);
    }
    result
}
fn update(name: &str, reference: Option<&str>) -> Result<()> {
    let dir = installed(name)?;
    if !git(&dir, &["status", "--porcelain", "--untracked-files=all"])?.is_empty() {
        return Err("plugin has local modifications; refusing update".into());
    }
    let branch = git(&dir, &["rev-parse", "--abbrev-ref", "HEAD"])?;
    if reference.is_none() && branch.trim() == "HEAD" {
        println!(
            "{name} pinned {}",
            git(&dir, &["rev-parse", "HEAD"])?.trim()
        );
        return Ok(());
    }
    let commit = if let Some(reference) = reference {
        resolve(&dir, reference)?
    } else {
        let upstream = git(
            &dir,
            &[
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{upstream}",
            ],
        )?;
        let branch = upstream
            .trim()
            .strip_prefix("origin/")
            .ok_or("plugin must track origin")?;
        resolve(&dir, &format!("refs/heads/{branch}"))?
    };
    let (candidate_name, _) = candidate(&dir, &commit)?;
    if candidate_name != name {
        return Err("updated plugin name changed".into());
    }
    if reference.is_some() {
        git(&dir, &["checkout", "--detach", &commit, "--"])?;
    } else {
        git(&dir, &["merge", "--ff-only", "--no-edit", &commit])?;
    }
    println!("updated {name} {commit}");
    Ok(())
}
fn info(name: &str, check: bool) -> Result<()> {
    let dir = installed(name)?;
    let (manifest_name, entry) = work_manifest(&dir)?;
    if manifest_name != name {
        return Err("plugin name does not match installation".into());
    }
    let commit = git(&dir, &["rev-parse", "HEAD"])?;
    let actual = git(&dir, &["hash-object", "--no-filters", "--", &entry])?;
    let expected = tree_blob(&dir, "HEAD", &entry)?;
    let clean = git(&dir, &["status", "--porcelain", "--untracked-files=all"])?.is_empty()
        && actual.trim() == expected;
    println!(
        "source\t{}\ncommit\t{}\nentry\t{}\nhash\t{} (Git blob)\nstatus\t{}",
        git(&dir, &["remote", "get-url", "origin"])?.trim(),
        commit.trim(),
        entry,
        actual.trim(),
        if clean { "clean" } else { "modified" }
    );
    if check && !clean {
        return Err("plugin has local modifications".into());
    }
    Ok(())
}
pub fn marketplace(args: &[OsString]) -> i32 {
    if !args.is_empty() && !(args.len() == 1 && (args[0] == "ls" || args[0] == "list")) {
        eprintln!("maw: usage: maw marketplace [ls|list]");
        return 2;
    }
    println!("NAME\tSOURCE\nherdr\t{HERDR}");
    0
}
pub fn run(args: &[OsString]) -> Option<i32> {
    let verb = args.first()?.to_str()?;
    if !matches!(verb, "install" | "update" | "info" | "check") {
        return None;
    }
    let valid = (args.len() == 2
        || (matches!(verb, "install" | "update") && args.len() == 4 && args[2] == "--ref"))
        && args.iter().all(|s| s.to_str().is_some());
    if !valid {
        eprintln!("maw: usage: maw plugin {verb} <source|name> [--ref REF]");
        return Some(2);
    }
    let target = args[1].to_str().unwrap();
    let reference = args.get(3).and_then(|s| s.to_str());
    let result = match verb {
        "install" => install(target, reference),
        "update" => update(target, reference),
        _ => info(target, verb == "check"),
    };
    Some(match result {
        Ok(()) => 0,
        Err(e) => {
            eprintln!("maw: {e}");
            1
        }
    })
}
