# Changelog

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
