<p align="center"><img src="assets/skin/icon.svg" width="96" alt="HyperTerminal"></p>

# HyperTerminal

A persistent drop-down terminal and AI-agent session hub for KDE Plasma 6.
HyperTerminal combines a custom dark rust theme with Yakuake, Konsole, and tmux.
Open it with Backtick, select an agent or shell, and move sessions between the
console and standalone windows without restarting them.

## Features

- HyperTerminal launcher, Konsole profile, keyboard map, SVG skin, and desktop icon.
- Interactive selector for installed Codex, Claude, Grok, Kimi, Agy, OpenCode, and Fish shell sessions.
- Move running tmux sessions between windows; focus existing external Konsole sessions.
- Restore saved sessions after reboot using each agent's native continuation option.
- Save Wayland clipboard images and copy a shell-quoted path for agent prompts.
- User-level installer with dated backups; no root installation required.

## Requirements

Linux with KDE Plasma 6 on Wayland, Python 3, Bash, Fish, Yakuake, Konsole,
tmux, fzf, ripgrep, Qt 6 qdbus (`qdbus6`), wl-clipboard, procps, GNU coreutils,
and util-linux. `notify-send` and FiraCode Nerd Font Mono are optional.
Install the agent CLIs you want separately and put them on PATH.
This initial release uses standard `~/.config`, `~/.local/share`, and
`~/.local/bin` locations. Home paths containing spaces or shell metacharacters
listed by the installer are currently unsupported.

## Install

```bash
git clone https://github.com/supere989/HyperTerminal.git
cd HyperTerminal
python3 install.py --dry-run
python3 install.py
```

The installer merges HyperTerminal settings into your Yakuake and KDE shortcut
configuration, overrides the Yakuake menu/autostart entry with HyperTerminal,
and enables its user session persistence service. It saves replaced files and
a manifest under `~/.local/share/hyperterminal/backups/`.
Log out and back in for desktop shortcuts to reload. You can also run
`~/.local/bin/hyperterminal` directly. The installation keeps live terminals
running and preserves the legacy socket if existing sessions are detected.

For staged installation without desktop activation: `python3 install.py --no-activate`.
To reverse a file installation, run `python3 restore-install.py BACKUP_DIRECTORY`.
This restores backed-up files and removes newly installed files; it does not
terminate sessions or delete their state. Reload user systemd and log in again
after restoring. If the service did not exist before installation, disable it
with `systemctl --user disable hyperterminal-session-persistence.service` first.

## Controls

| Key | Action |
| --- | --- |
| Backtick | Open or retract HyperTerminal |
| Ctrl+Alt+Backtick | Insert a literal backtick |
| Ctrl+Shift+C / Ctrl+Shift+V | Copy / paste |
| Meta+Shift+V | Save clipboard image and copy its path; paste with Ctrl+Shift+V |
| + / Ctrl+Shift+T | Open session selector in a new tab |
| Ctrl+B, then O | Move managed session into standalone Konsole |
| Ctrl+B, then D | Detach while leaving session running |

## Agent detection and history

The selector refreshes installed-agent detection whenever it opens or returns
from a session. It searches PATH and common per-user installation directories:
`~/.local/bin`, `~/.grok/bin`, `~/.kimi-code/bin`, `~/.opencode/bin`,
`~/.npm-global/bin`, and `~/.cargo/bin`. Only detected supported CLIs get new
session actions; no login or provider request is made during detection.
Supported adapters are Codex, Claude, Grok, Kimi, Agy, and OpenCode.

The list offers:

- **New session** for each installed agent.
- **Continue latest** using that agent's native continuation command.
- **Choose previous conversation** using native pickers for Codex, Claude, and Kimi.
- **Recent conversations** with exact IDs and original project directories for
  Codex, Claude, Grok, Kimi, and OpenCode (up to 20 per agent).
- **Running managed sessions** to move/reattach, and **saved HyperTerminal sessions**
  to recreate using their persisted record. Uninstalled agents keep their saved records.

History reads metadata from local agent stores; OpenCode uses its local JSON
session-list command with a timeout. Discovery does not edit agent histories.
Agy currently offers native latest-conversation continuation rather than a
history list. Native pickers provide access beyond the recent-history limit.

Selecting an exact conversation stores its ID with the HyperTerminal record.
Snapshots and reboot restoration preserve that ID. Reselecting an already
managed exact conversation reuses it instead of creating another process.
If its executable or project directory is unavailable, restoration is deferred
and the record is retained. Existing version-1 records remain supported.

The optional selector `hyperterminal-agents` uses the same managed session flow.
`hyperterminal-agents codex` creates a managed Codex session. Diagnostics:

```bash
hyperterminal-catalog list             # detected installed agents and executable paths
hyperterminal-catalog history          # recent local conversation metadata as JSON
hyperterminal-tab --list               # selector rows without launching an agent
hyperterminal-session list-saved       # saved sessions which are not currently running
```

## Agent permissions and restoration

**Agent launches use power mode by default.** The launchers pass permission
bypass/automatic approval flags: Codex `--dangerously-bypass-approvals-and-sandbox`,
Claude and Agy `--dangerously-skip-permissions`, Grok `--always-approve`, and
Kimi and OpenCode `--auto`. Choose a shell and launch the plain CLI yourself when you want
its normal approval policy. HyperTerminal does not install or authenticate agents.
Agent CLI flag compatibility depends on the versions you install.

Session records live in `~/.local/state/hyperterminal/`. Restoration recreates
processes in their saved directory; a reboot cannot preserve an in-memory process.
Exact-history selections resume their persisted conversation ID. Sessions started
as new, through a native picker, or through Continue latest retain the native
latest-conversation restoration behavior; they are not bound to an exact ID.
Codex uses `resume --last`; the other adapters use `--continue`.
External non-tmux sessions can be focused but cannot be reparented.
Images are saved under `~/Pictures/HyperTerminal Clipboard/` (or `XDG_PICTURES_DIR`).

## Development

```bash
python3 tests/verify.py
python3 tests/detection.py
```

Checks cover Bash syntax, asset parsing, isolated installer backup/restore,
and actual tmux shell-session creation, snapshot, restoration, tab queue,
and cleanup. Agent checks cover discovery, exact resume arguments, reattachment,
missing-agent recovery, and legacy records. Desktop appearance and agent CLI compatibility require a real
Plasma session with the relevant dependencies.

Project layout: `bin/` launchers; `assets/` theme/profile; `config/` integration;
`desktop/` menu templates; `systemd/` persistence service.

## License and credits

GPL-3.0-or-later. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
HyperTerminal uses KDE Yakuake and Konsole as its terminal engines.
