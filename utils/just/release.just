set working-directory := '../..'

# Read-only upstream CalVer preview; no tags or uploads.
preview:
    /usr/bin/time -p python3 utils/scripts/release.py

# Derive a deterministic plan from a successful canonical alpha CI run.
prepare ci_run output:
    /usr/bin/time -p python3 utils/scripts/release.py prepare --ci-run {{quote(ci_run)}} --output {{quote(output)}}

# CI normally invokes this after all sixteen archives pass smoke verification.
publish plan assets:
    /usr/bin/time -p python3 utils/scripts/release.py publish --plan {{quote(plan)}} --assets {{quote(assets)}}
