set working-directory := '../..'

# Read-only CalVer preview and GitHub issue/PR-driven release notes; no tag or upload.
preview:
    /usr/bin/time -p python3 utils/scripts/release.py

# Only after explicit human approval of this exact tag AND merged alpha SHA.
publish tag commit:
    /usr/bin/time -p python3 utils/scripts/release.py --publish --approve {{quote(tag)}} --commit {{quote(commit)}}
