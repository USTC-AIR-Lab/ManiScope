# Public-source cleanup

This revision removes internal working reports and the obsolete localized scene-document generator,
translates first-party comments and diagnostic text, and replaces deployment-specific path checks
with generic user-home checks. Optional private regexes can be stored one per line in
`configs/private/anonymity_patterns.txt`; blank lines and comments are ignored. Invalid patterns
fail validation. Do not commit deployment names in the public checker.

Before refreshing the byte-level protocol lock, the release was compared to the preceding
source snapshot: all instruction pools (excluding unused `_note` metadata), all seed files,
scene membership/parameters, and executable Python AST structure excluding text constants
were preserved. Existing evaluation/control modules contain no numeric or control-flow changes.
English telemetry labels replace localized labels; private historical logs need explicit conversion.
This is a source/documentation cleanup within formal48-v1, not a new score or rollout claim.

The bundled agent bridge retains the experiment prompt/tool schema and motion-limit module.
Its portable account-budget implementation and error-handling changes are documented in
EXTERNAL_AGENT.md. CPU contract tests do not establish GPU simulation or live API compatibility.

Upstream license notices, including original author names, are retained. Internal records are
not part of the released source. Removing files from this snapshot does not erase Git history;
an anonymous artifact should be exported from the reviewed tree without `.git`.
