# Security

Do not commit API tokens, SSH private keys, local.env, checkpoints or private gateway configuration.
Use environment variables or an ignored private token file. The repository checks recognizable
credential patterns; these checks are heuristic and do not establish absence of all secrets.

Run inference services on loopback or a trusted private network. Several inherited transports use
pickle or unauthenticated local HTTP and must not be exposed directly to the public internet.
Treat local.env as executable shell configuration. Review it before sourcing.

If a secret is exposed, revoke it and inspect the Git history; deleting only the current file is
insufficient. Before public hosting, enable a private vulnerability-reporting channel on that host.
