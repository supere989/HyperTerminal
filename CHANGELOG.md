# Changelog
## 0.4.0
- Add a Dolphin "Activities" folder submenu with ansr-claude, Codex, Agy, Grok, and Kimi power entries.
- Open a folder's running session, exact native conversation, dormant record, or a new session, in that order.
- Recommend the enclosing project (git, project registry, or existing session) before opening a child folder.
- Attach opened sessions in a new HyperTerminal tab, or in Konsole when Yakuake is not running.
- Ledger every open, cancel, and failure; summarise with `hyperterminal-open --stats`.
- Add `list-records` and `queue-tab` session commands and the `hyperterminal open` binary command.
- Reject option-like agent names so `--help` never creates a session record.

## 0.3.0

- Add a single Rust executable embedding the installer, runtime, and theme assets.
- Check dependencies before operational commands; show a read-only doctor report.
- Ask permission before package-manager downloads and installation, defaulting to No.
- Support Arch/Garuda, Debian/Ubuntu, and Fedora package mappings.
- Handle terminal and KDE desktop confirmation and administrator authentication.
- Recheck dependencies after installation and defer deployment on failure.
- Atomically deploy files, including upgrades to the running executable, with backups.
- Route binary-install menu/autostart entries through the dependency checker.
- Handle distribution-specific Qt 6 qdbus names.

## 0.2.0

- Detect installed coding agents on PATH and common user installation paths.
- Add OpenCode and dynamically list new, latest, and native-picker actions.
- List recent native conversations and dormant HyperTerminal records.
- Persist exact conversation IDs and reuse existing managed conversations.
- Preserve version-1 records and defer unavailable-agent restoration.
- Avoid overwriting dormant records when naming new sessions.
- Preserve pending tab queues when restoring additional sessions.
- Use the same managed persistence flow for the standalone agent selector.

## 0.1.0

- Package the original desktop installation as the public HyperTerminal project.
- Brand selectors, launchers, window titles, status bar, desktop entries, and theme.
- Replace workstation-specific paths with installer-rendered configuration.
- Add backup/restore installation and continuous verification.
- Preserve Base64 padding when reading restoration records.
- Make empty tab queues succeed and use TMUX_PANE for pop-out detection.
- Retain compatibility with existing live legacy tmux sessions during installation.
