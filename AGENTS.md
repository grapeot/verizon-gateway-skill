# AGENTS.md

## Working Conventions

- **Language:** All code, documentation, tests, commit messages, and agent notes use English.
- **Hardware Framing:** Target hardware is the Wistron NeWeb Corporation (WNC) **LVSKIHP** Verizon gateway. Do not claim universal support for unverified models or firmware.
- **Progress Tracking:** Maintain `docs/working.md` as the active implementation checklist, decision log, and open-validation tracker whenever making design or code changes.

## Public / Private Separation

- Keep this repository strictly generic and safe for public MIT distribution.
- Use only synthetic placeholders (`http://gateway.example`, `op://your-vault/your-item/your-field`, `/path/to/project`).
- Never commit or log owner handles, local topology, private or public IP addresses, home paths, serial numbers, phone numbers, real secret-manager paths, raw HTTP response bodies, request URLs, or captured gateway logs.
- Real gateway URLs, credential commands, supervision paths, and LAN topology belong exclusively in a host-owned private overlay outside git, alongside gitignored runtime storage (such as `data/`).

## Verification and Git Discipline

- Default branch is `master`.
- Run the offline test suite in `.venv` managed by `uv` before marking implementation tasks complete. CI must remain 100% offline with zero live router or credential dependencies; live hardware tests are strictly opt-in.
- Stage specific task files only (`git add <file>`). Create commits or push to remotes only when explicitly authorized by the user.
