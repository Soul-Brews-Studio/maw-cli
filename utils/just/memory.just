set working-directory := '../..'

# Incrementally index local conversations once; active sessions can remain changed.
index:
    /usr/bin/time -p relic index

pending:
    /usr/bin/time -p relic pending

session id:
    /usr/bin/time -p relic session {{quote(id)}} --json
