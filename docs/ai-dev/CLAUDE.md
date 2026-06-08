## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- ALWAYS read graphify-out/GRAPH_REPORT.md before reading any source files, running grep/glob searches, or answering codebase questions. The graph is your primary map of the codebase.
- IF graphify-out/wiki/index.md EXISTS, navigate it instead of reading raw files
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- Install: `uv tool install graphifyy` (PyPI package is `graphifyy`, CLI is `graphify`). GitHub: https://github.com/safishamsi/graphify
- In Debian WSL: ensure PATH includes `~/.local/bin` — run as `~/.local/bin/graphify update .` or add to ~/.bashrc
