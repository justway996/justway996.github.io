# Continue development

Status: in progress. This is a local-verification release, not an accepted full environment migration product.

Implemented: explicit source roots, SQLite/WAL backup, AES-GCM volumes, DPAPI/local and offline recovery keys, isolated restoration, readable chats, link/path reports, Chinese GUI/CLI, opt-in Windows scheduling code, and the official Quark CLI protocol adapter.

Validation: 58 unittest executions passed on Windows Python 3.12; packaged exe help/GUI smoke passed before the latest rebuild. Representative real files were encrypted/restored and chat messages exported. The real cloud account, clean Windows migration, project startup and long-running scheduling are not yet accepted. Unit tests use a LocalDrive fake only for transport contracts.

Next work:

1. Complete WSL and official Quark installation, OAuth and a real upload/download/hash probe in a user-selected directory. Adapter behavior must be checked against the actual installed CLI version.
2. Recheck and improve full environment coverage, dependency inventories, semantic handoff hashes/freshness and vault path mappings. Current reports deliberately do not mark runtime/project/handoff checks true automatically.
3. Run a clean Windows/new Codex session restoration and project validation. Preserve original user instructions, project cards and rule stages; do not activate every restored automation.

Development: install the project, set PYTHONPATH=src, then run `python -m unittest discover -s tests -v`. `python -m codex_backup gui-smoke` checks widget construction. Build with packaging/build.ps1; current pinned dependency versions are in requirements-lock.txt.

Do not commit real config files, recovery keys, database copies, chats or backup packages. Public source publication belongs in the repository's dedicated subdirectory; keep its existing website unchanged.
