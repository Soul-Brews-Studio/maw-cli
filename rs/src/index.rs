use serde_json::{json, Value};
use std::collections::{BTreeMap, HashSet};
use std::ffi::OsString;
use std::fs::File;
use std::io::{self, Read};

const MAX_BYTES: u64 = 64 * 1024 * 1024;

fn read_input(path: &OsString) -> Result<Vec<u8>, String> {
    let reader: Box<dyn Read> = if path == "-" {
        Box::new(io::stdin())
    } else {
        let file = File::open(path).map_err(|error| error.to_string())?;
        if file.metadata().map_err(|error| error.to_string())?.len() > MAX_BYTES {
            return Err("input exceeds 64 MiB".into());
        }
        Box::new(file)
    };
    let mut bytes = Vec::new();
    reader
        .take(MAX_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|error| error.to_string())?;
    if bytes.len() as u64 > MAX_BYTES {
        return Err("input exceeds 64 MiB".into());
    }
    Ok(bytes)
}

fn field<'a>(value: &'a Value, key: &str) -> Result<&'a str, String> {
    value
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| format!("missing or non-string {key}"))
}

fn build(bytes: &[u8]) -> Result<Value, String> {
    let input = std::str::from_utf8(bytes).map_err(|error| error.to_string())?;
    let mut postings: BTreeMap<String, Vec<usize>> = BTreeMap::new();
    let mut symbols = HashSet::new();
    let (mut records, mut text_bytes) = (0usize, 0usize);
    for (line_number, line) in input.split('\n').enumerate() {
        if line.trim_matches(|c| matches!(c, ' ' | '\t' | '\r')).is_empty() {
            continue;
        }
        let record: Value = serde_json::from_str(line)
            .map_err(|error| format!("line {}: {error}", line_number + 1))?;
        if record.get("jsonrpc").and_then(Value::as_str) != Some("2.0") {
            return Err(format!("line {}: expected jsonrpc 2.0", line_number + 1));
        }
        let content = &record["result"]["structuredContent"];
        let file = field(content, "file")?;
        let symbol = field(content, "symbol")?;
        let text = field(content, "text")?;
        if file.is_empty() || symbol.is_empty() || file.contains('\0') || symbol.contains('\0') {
            return Err("file and symbol must be nonempty and contain no NUL".into());
        }
        symbols.insert((file.to_owned(), symbol.to_owned()));
        text_bytes += text.len();
        let terms: HashSet<String> = text
            .split(|c: char| !c.is_ascii_alphanumeric() && c != '_')
            .filter(|term| !term.is_empty())
            .map(str::to_ascii_lowercase)
            .collect();
        for term in terms {
            postings.entry(term).or_default().push(records);
        }
        records += 1;
    }
    let mut checksum = 14695981039346656037u64;
    let mut posting_count = 0usize;
    for (term, documents) in &postings {
        posting_count += documents.len();
        for byte in format!("{}:{}\n", term, documents.len()).bytes() {
            checksum = (checksum ^ u64::from(byte)).wrapping_mul(1099511628211);
        }
    }
    Ok(
        json!({"records": records, "input_bytes": bytes.len(), "text_bytes": text_bytes,
        "unique_symbols": symbols.len(), "unique_terms": postings.len(), "postings": posting_count,
        "checksum": format!("{checksum:016x}")}),
    )
}

pub fn run(args: &[OsString]) -> i32 {
    if args.len() != 1 {
        eprintln!("maw: usage: maw index FILE|-");
        return 2;
    }
    match read_input(&args[0]).and_then(|bytes| build(&bytes)) {
        Ok(summary) => {
            println!("{summary}");
            0
        }
        Err(error) => {
            eprintln!("maw: index: {error}");
            1
        }
    }
}
