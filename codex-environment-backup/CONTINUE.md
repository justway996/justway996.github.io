# Continue development

Status: in progress. Version 0.1.2 has passed a representative Quark round trip and a default 32 MiB multi-volume round trip; full environment migration is not yet accepted.

Implemented: explicit source roots, SQLite/WAL backup, AES-GCM volumes, DPAPI/local and offline recovery keys, isolated restoration, readable chats, link/path reports, Chinese GUI/CLI, opt-in Windows scheduling code, and the official Quark CLI protocol adapter.

Validation: 65 unittest executions passed on Windows Python 3.12. Three harmless files passed real Quark Unicode/space names, pagination (page-size 1), download hashes and new-process authorization. A representative encrypted snapshot containing 412 files was uploaded, rediscovered by a fresh client, downloaded, authenticated and restored; its older tool source passed 53 tests. The final private-HOME/read-only-CLI/temporary-download revision also fetched and authenticated that real snapshot. A 64 MiB volume uploaded but download failed with error 23018, download file size limit 52428800. Default volumes are now 32 MiB; a synthetic 52 MiB source produced two parts, both published, independently rediscovered, downloaded and authenticated. Legacy 64 MiB local readers remain compatible. Clean Windows/new account, all projects and long-running scheduling remain unverified.

Next work:

1. Use the tested deployment contract in docs/QUARK-SETUP.zh-CN.md: dedicated non-root WSL user, read-only official CLI, private working directory and HOME. Actual CLI 1.0.24-29460f9 provides download --output-dir; its bundled read-file documentation describes another variant. Do not switch commands based only on that document. Keep default volumes at 32 MiB for the observed 50 MiB download limit. Verify expiry, interruptions and opt-in scheduling next.
2. Recheck and improve full environment coverage, dependency inventories, semantic handoff hashes/freshness and vault path mappings. Current reports deliberately do not mark runtime/project/handoff checks true automatically.
3. Run a clean Windows/new Codex session restoration and project validation. Preserve original user instructions, project cards and rule stages; do not activate every restored automation.

The current machine's metadata-only inventory found about 26.5 GiB before exclusions, including old account-recovery duplicates and dependency links. This is an inventory, not an uploaded full backup. Keep backup outputs/recovery keys outside selected source roots; preserve required source and assets while classifying rebuildable dependencies explicitly.

Development: install the project, set PYTHONPATH=src, then run `python -m unittest discover -s tests -v`. `python -m codex_backup gui-smoke` checks widget construction. Build with packaging/build.ps1; current pinned dependency versions are in requirements-lock.txt.

Do not commit real config files, recovery keys, database copies, chats or backup packages. Public source publication belongs in the repository's dedicated subdirectory; keep its existing website unchanged.
