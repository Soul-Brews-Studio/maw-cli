#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
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
# Host binaries must be excluded; both listing built-ins must win PATH collisions.
for host in go rs js zig plugin plugins marketplace; do
    cat > "$tmp/plugins/maw-$host" <<'HOST'
#!/bin/sh
printf 'host ran\n' >> "$MAW_SMOKE_MARKER"
exit 91
HOST
    chmod +x "$tmp/plugins/maw-$host"
done
MAW_SMOKE_MARKER="$tmp/marker"
export MAW_SMOKE_MARKER

# Isolate discovery from any real, potentially operational local plugins.
run() {
    if [ -n "$entry" ]; then
        HOME="$tmp/home" MAW_HOME="$tmp/home/.maw" MAW_PLUGINS_DIR="$tmp/home/.maw/plugins" PATH="$tmp/plugins" "$maw" "$entry" "$@"
    else
        HOME="$tmp/home" MAW_HOME="$tmp/home/.maw" MAW_PLUGINS_DIR="$tmp/home/.maw/plugins" PATH="$tmp/plugins" "$maw" "$@"
    fi
}
run > "$tmp/default"
run --help > "$tmp/help"
cmp "$tmp/default" "$tmp/help"
for argument in help -h; do
    run "$argument" > "$tmp/root-help"
    cmp "$tmp/help" "$tmp/root-help"
done
grep -q 'Usage: maw' "$tmp/help"
[ "$(grep -c '^  plugin[[:space:]]' "$tmp/help")" -eq 1 ] || fail 'root help must show one canonical plugin command'
if grep -q '^  plugins[[:space:]]' "$tmp/help"; then
    fail 'root help shows the compatibility plugins alias'
fi
grep -q 'probe' "$tmp/help"
run version > "$tmp/version"
grep -q '^maw .' "$tmp/version"
run plugins > "$tmp/plugins-list"
grep -q '^no plugins installed$' "$tmp/plugins-list"
run plugin ls > "$tmp/plugin-ls"
run plugins ls > "$tmp/plugins-ls"
cmp "$tmp/plugins-list" "$tmp/plugin-ls"
cmp "$tmp/plugins-list" "$tmp/plugins-ls"
run plugin list > "$tmp/plugin-list"
cmp "$tmp/plugin-ls" "$tmp/plugin-list"
run marketplace > "$tmp/marketplace"
grep -q 'Soul-Brews-Studio/maw-herdr-plugin' "$tmp/marketplace"
[ ! -e "$tmp/home" ] || fail 'listing created plugin/config directories'
if grep -q '^  index[[:space:]]' "$tmp/help" || grep -q '^index[[:space:]]' "$tmp/plugin-ls"; then
    fail 'removed index command leaked into help/listing'
fi
status=0
printf '' | run index - > "$tmp/out" 2> "$tmp/err" || status=$?
[ "$status" -eq 2 ] || fail "removed index command exit: $status"
grep -q 'unknown command' "$tmp/err"
status=0
run help index > "$tmp/out" 2> "$tmp/err" || status=$?
[ "$status" -eq 2 ] || fail "removed index help exit: $status"
grep -q 'unknown command' "$tmp/err"
run plugin --help > "$tmp/list-help"
run help plugin > "$tmp/list-help-alias"
cmp "$tmp/list-help" "$tmp/list-help-alias"
grep -q 'Usage: maw plugin ' "$tmp/list-help"
run plugins --help > "$tmp/plural-help"
run help plugins > "$tmp/plural-help-alias"
cmp "$tmp/plural-help" "$tmp/plural-help-alias"
grep -q 'Usage: maw plugins' "$tmp/plural-help"
for name in plugin plugins; do
    for argument in install update info check LS; do
        status=0
        run "$name" "$argument" > "$tmp/out" 2> "$tmp/err" || status=$?
        [ "$status" -eq 2 ] || fail "unsupported plugin operation: $name $argument: $status"
        grep -q 'usage: maw' "$tmp/err"
    done
    status=0
    run "$name" ls extra > "$tmp/out" 2> "$tmp/err" || status=$?
    [ "$status" -eq 2 ] || fail "extra plugin arguments: $name: $status"
done
status=0
run plugin > "$tmp/out" 2> "$tmp/err" || status=$?
[ "$status" -eq 2 ] || fail "missing plugin subcommand: $status"
grep -q 'usage: maw plugin ' "$tmp/err"
for host in go rs js zig; do
    if grep -q "^$host[[:space:]]" "$tmp/plugins-list"; then
        fail "host binary discovered as plugin: $host"
    fi
    if grep -q "^  $host[[:space:]]" "$tmp/help"; then
        fail "host binary listed in help: $host"
    fi
    status=0
    run "$host" > "$tmp/out" 2> "$tmp/err" || status=$?
    [ "$status" -eq 2 ] || fail "host command exit: $host: $status"
    grep -q 'unknown command' "$tmp/err"
    status=0
    run help "$host" > "$tmp/out" 2> "$tmp/err" || status=$?
    [ "$status" -eq 2 ] || fail "host help exit: $host: $status"
    grep -q 'unknown command' "$tmp/err"
done
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
printf 'smoke: help, version, plugin ls aliases/collisions, discovery, plugin argv/streams/exit OK\n'

# plugin ls -v renders the maw-rs table: tier sections, per-section column
# widths measured on the raw cell (escapes included, as maw-rs does), and a
# trailing active count.
mkdir -p "$tmp/home/.maw/plugins/demo"
cat > "$tmp/home/.maw/plugins/demo/plugin.json" <<'PLUGINJSON'
{"name":"demo","version":"1.2.3","tier":"extra","entry":"index.ts","runtime":"bun-dev","target":"js","cli":{"command":"demo","interactive":true}}
PLUGINJSON
: > "$tmp/home/.maw/plugins/demo/index.ts"
run plugin ls -v > "$tmp/plv" 2>"$tmp/plv-err" || fail "plugin ls -v exit"
# Only the JS port renders the maw-rs table today; probe rather than hardcode a
# port, so this starts covering go/rs/zig the moment they render it too.
if grep -q 'extra.*(1)' "$tmp/plv"; then
grep -q '^name  *version  *tier  *surfaces  *dir' "$tmp/plv" || fail 'plugin ls -v must print a header row'
grep -q '^─' "$tmp/plv" || fail 'plugin ls -v must print a separator row'
grep -q 'cli:demo' "$tmp/plv" || fail 'plugin ls -v must print the surfaces column'
grep -q '^1 active$' "$tmp/plv" || fail 'plugin ls -v must end with the active count'
    printf 'smoke: plugin ls -v table sections, header/separator, surfaces, active count OK\n'
else
    printf 'smoke: plugin ls -v table not rendered by this port, skipped\n'
fi
rm -rf "$tmp/home/.maw/plugins/demo"

# locate: registry read is isolated to MAW_HOME and must never require tmux.
# Only the JS port implements it today; probe root help rather than hardcoding a
# port, so this block starts covering go/rs/zig the moment they register it.
if grep -q '^  locate[[:space:]]' "$tmp/help"; then
mkdir -p "$tmp/home/.maw"
cat > "$tmp/home/.maw/oracles.json" <<'REGISTRY'
{"oracles":[
 {"name":"alpha","org":"acme","repo":"alpha-oracle","local_path":"/checkouts/alpha"},
 {"name":"alphabet","org":"acme","repo":"alphabet-oracle","local_path":"/checkouts/alphabet"},
 {"name":"dup","org":"one","repo":"dup-oracle","local_path":"/checkouts/one-dup"},
 {"name":"dup","org":"two","repo":"dup-oracle","local_path":"/checkouts/two-dup"}
]}
REGISTRY
[ "$(run locate alpha --path)" = '/checkouts/alpha' ] || fail 'locate exact name'
[ "$(run locate acme/alphabet-oracle --path)" = '/checkouts/alphabet' ] || fail 'locate org/repo slug'
[ "$(run locate alphab --path)" = '/checkouts/alphabet' ] || fail 'locate unique prefix'
[ "$(run locate two/dup-oracle --path)" = '/checkouts/two-dup' ] || fail 'locate disambiguates by slug'
run locate alpha --json > "$tmp/locate-json"
grep -q '"local_path":"/checkouts/alpha"' "$tmp/locate-json" || fail 'locate --json shape'
for invalid in '' 'alpha --path --json' 'alpha --bogus'; do
    status=0
    # shellcheck disable=SC2086
    run locate $invalid > "$tmp/out" 2> "$tmp/err" || status=$?
    [ "$status" -eq 2 ] || fail "locate usage exit: '$invalid': $status"
done
status=0
run locate dup > "$tmp/out" 2> "$tmp/err" || status=$?
[ "$status" -eq 1 ] || fail "locate ambiguous exit: $status"
grep -q 'matches 2 oracles' "$tmp/err" || fail 'locate ambiguous must list candidates'
status=0
run locate absent > "$tmp/out" 2> "$tmp/err" || status=$?
[ "$status" -eq 1 ] || fail "locate miss exit: $status"
rm -f "$tmp/home/.maw/oracles.json"
status=0
run locate alpha > "$tmp/out" 2> "$tmp/err" || status=$?
[ "$status" -eq 1 ] || fail "locate missing registry exit: $status"
grep -q '0 registered' "$tmp/err" || fail 'locate missing registry must report an empty registry'
printf 'smoke: locate name/slug/prefix tiers, ambiguity, usage, missing registry OK\n'
else
    printf 'smoke: locate not registered by this port, skipped\n'
fi

# default: route unmatched verbs to a plugin, without shadowing what already
# resolves. Probe support so ports lacking the command skip.
if run default >/dev/null 2>&1; then
    [ "$(run default)" = 'none' ] || fail 'default must report none when unset'
    mkdir -p "$tmp/home/.maw/plugins/router"
    cat > "$tmp/home/.maw/plugins/router/plugin.json" <<'ROUTER'
{"name":"router","version":"1.0.0","tier":"extra","entry":"index.ts","runtime":"bun-dev","target":"js","cli":{"command":"router","interactive":true}}
ROUTER
    : > "$tmp/home/.maw/plugins/router/index.ts"
    cat > "$tmp/plugins/bun" <<'FAKEBUN'
#!/bin/sh
shift
printf 'routed:%s\n' "$*"
FAKEBUN
    chmod +x "$tmp/plugins/bun"
    run default set router > "$tmp/dset" || fail 'default set exit'
    grep -q '^default: router' "$tmp/dset" || fail 'default set must confirm the plugin'
    [ "$(run default)" = 'router' ] || fail 'default must report the configured plugin'
    [ "$(run made-up-verb)" = 'routed:made-up-verb' ] || fail 'unmatched verb must route to the default'
    run --help | grep -q '^Default: router' || fail 'help must disclose the routing'
    run plugin ls >/dev/null || fail 'built-ins must still win over the default'
    [ "$(run version)" != 'routed:version' ] || fail 'default must not shadow a built-in'
    status=0; run default set nosuch >/dev/null 2>&1 || status=$?
    [ "$status" -eq 1 ] || fail "default set must refuse an unknown plugin: $status"
    for invalid in 'bogus' 'set'; do
        status=0
        run default $invalid >/dev/null 2>&1 || status=$?
        [ "$status" -eq 2 ] || fail "default usage exit: '$invalid': $status"
    done
    run default unset >/dev/null || fail 'default unset exit'
    [ "$(run default)" = 'none' ] || fail 'default unset must clear the routing'
    rm -rf "$tmp/home/.maw/plugins/router"
    printf 'smoke: default set/show/unset, routing, built-in precedence, help disclosure OK\n'
else
    printf 'smoke: default not implemented by this port, skipped\n'
fi

if [ -n "$entry" ]; then
    python3 utils/scripts/plugin-smoke.py -- "$maw" "$entry"
    python3 utils/scripts/dispatch-smoke.py -- "$maw" "$entry"
    python3 utils/scripts/lifecycle-smoke.py -- "$maw" "$entry"
else
    python3 utils/scripts/plugin-smoke.py -- "$maw"
    python3 utils/scripts/dispatch-smoke.py -- "$maw"
    python3 utils/scripts/lifecycle-smoke.py -- "$maw"
fi
