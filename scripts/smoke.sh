#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
maw="${1:-$(pwd)/bin/maw-go}"
entry="${2:-}"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

fail() { printf 'smoke: %s\n' "$*" >&2; exit 1; }
[ -x "$maw" ] || fail "build executable first: $maw"
mkdir "$tmp/plugins"
cat > "$tmp/plugins/maw-probe" <<'PLUGIN'
#!/bin/sh
printf 'ran\n' >> "$MAW_SMOKE_MARKER"
if [ "$#" -eq 1 ] && [ "$1" = '--help' ]; then
    printf 'probe help\n'
    exit 0
fi
[ "$#" -eq 3 ] || exit 90
[ "$1" = 'two words' ] && [ "$2" = '' ] && [ "$3" = '*.go' ] || exit 91
IFS= read -r line
printf 'stdin=%s\n' "$line"
printf 'probe stderr\n' >&2
exit 7
PLUGIN
chmod +x "$tmp/plugins/maw-probe"
MAW_SMOKE_MARKER="$tmp/marker"
export MAW_SMOKE_MARKER

# Isolate discovery from any real, potentially operational local plugins.
run() {
    if [ -n "$entry" ]; then
        PATH="$tmp/plugins" "$maw" "$entry" "$@"
    else
        PATH="$tmp/plugins" "$maw" "$@"
    fi
}
run > "$tmp/default"
run --help > "$tmp/help"
cmp "$tmp/default" "$tmp/help"
grep -q 'Usage: maw' "$tmp/help"
grep -q 'probe' "$tmp/help"
run version > "$tmp/version"
grep -q '^maw .' "$tmp/version"
run plugins > "$tmp/plugins-list"
grep -q 'probe.*external' "$tmp/plugins-list"
[ ! -e "$tmp/marker" ] || fail 'help/list executed a plugin'

status=0
run not-a-command > "$tmp/out" 2> "$tmp/err" || status=$?
[ "$status" -eq 2 ] || fail "unknown command exit: $status"
grep -q 'unknown command' "$tmp/err"

run help probe > "$tmp/plugin-help"
grep -q '^probe help$' "$tmp/plugin-help"
status=0
printf 'hello stdin\n' | run probe 'two words' '' '*.go' > "$tmp/out" 2> "$tmp/err" || status=$?
[ "$status" -eq 7 ] || fail "plugin exit/argv: $status"
grep -q '^stdin=hello stdin$' "$tmp/out"
grep -q '^probe stderr$' "$tmp/err"
printf 'smoke: help, version, discovery, plugin argv/streams/exit OK\n'
