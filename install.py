#!/usr/bin/env python3
"""Install HyperTerminal for the current user, backing up every replaced file."""
import argparse
import configparser
import datetime
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent

def merge_ini(path, sections):
    cfg = configparser.RawConfigParser(strict=False, delimiters=('=',))
    cfg.optionxform = str
    if path.exists(): cfg.read(path)
    for section, entries in sections.items():
        if not cfg.has_section(section): cfg.add_section(section)
        for key, value in entries.items(): cfg.set(section, key, value)
    out = io.StringIO()
    cfg.write(out, space_around_delimiters=False)
    return out.getvalue().encode()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-activate', action='store_true', help='Skip desktop cache and systemd activation')
    args = parser.parse_args()
    home = Path.home()
    bindir = home/'.local/bin'
    config = home/'.config'
    share = home/'.local/share'
    # This release installs into standard KDE paths; reject ambiguous XDG layouts.
    for key, expected in [('XDG_CONFIG_HOME', config), ('XDG_DATA_HOME', share)]:
        if os.environ.get(key) and Path(os.environ[key]) != expected:
            parser.error(f'{key} must be unset or {expected}')
    deps = ['python3','bash','fish','tmux','fzf','yakuake','konsole','qdbus6','rg','wl-copy','wl-paste','flock','base64','ps']
    qt_candidates = ['qdbus6', 'qdbus-qt6', '/usr/bin/qdbus6', '/usr/bin/qdbus-qt6', '/usr/lib/qt6/bin/qdbus', '/usr/lib64/qt6/bin/qdbus']
    missing = [name for name in deps if not (any(shutil.which(candidate) for candidate in qt_candidates) if name == 'qdbus6' else shutil.which(name))]
    if missing and not args.no_activate and not args.dry_run:
        parser.error('Missing dependencies: '+', '.join(missing))
    if missing: print('Dependencies to install: '+', '.join(missing))
    files = {}
    def render(source):
        # Quote command paths for Konsole/desktop parsers and tmux shell commands.
        return source.read_text().replace('@BIN_DIR@',str(bindir)).encode()
    if any(c in str(home) for c in ' "\'\\\n\r%'):
        parser.error('This release requires a home path without spaces, quotes, backslashes, or percent signs')
    for p in (ROOT/'bin').iterdir(): files[bindir/p.name] = (p.read_bytes(),0o755)
    binary_source = os.environ.get('HYPERTERMINAL_BINARY_SOURCE')
    if binary_source:
        files[bindir/'hyperterminal'] = (Path(binary_source).read_bytes(), 0o755)
    files[bindir/'agents'] = (b'#!/usr/bin/env bash\nexec "$HOME/.local/bin/hyperterminal-agents" "$@"\n',0o755)
    for p in (ROOT/'assets/konsole').iterdir():
        if p.suffix == '.keytab': continue
        files[share/'konsole'/p.name] = (render(p),0o644)
    files[share/'konsole/HyperTerminal.keytab'] = ((ROOT/'assets/konsole/HyperTerminal.keytab').read_bytes(),0o644)
    for p in (ROOT/'assets/skin').rglob('*'):
        if p.is_file(): files[share/'yakuake/skins/hyperterminal'/p.relative_to(ROOT/'assets/skin')] = (p.read_bytes(),0o644)
    files[share/'icons/hicolor/scalable/apps/hyperterminal.svg'] = ((ROOT/'assets/skin/icon.svg').read_bytes(),0o644)
    files[config/'hyperterminal/tmux.conf'] = (render(ROOT/'config/tmux.conf'),0o644)
    template = configparser.RawConfigParser()
    template.optionxform = str
    template.read(ROOT/'config/yakuakerc')
    files[config/'yakuakerc'] = (merge_ini(config/'yakuakerc',{s:dict(template[s]) for s in template.sections()}),0o600)
    files[config/'kglobalshortcutsrc'] = (merge_ini(config/'kglobalshortcutsrc',{
        'yakuake': {'_k_friendly_name':'HyperTerminal','toggle-window-state':'`,F12,Open/Retract HyperTerminal'},
        'services][hyperterminal-paste-image.desktop': {'_launch':'Meta+Shift+V'},
        'services][quake-paste-image.desktop': {'_launch':'none'},
    }),0o600)
    files[share/'applications/org.kde.yakuake.desktop'] = (render(ROOT/'desktop/org.kde.yakuake.desktop.in'),0o644)
    files[share/'applications/hyperterminal-paste-image.desktop'] = (render(ROOT/'desktop/hyperterminal-paste-image.desktop.in'),0o644)
    files[config/'autostart/org.kde.yakuake.desktop'] = (render(ROOT/'desktop/hyperterminal-autostart.desktop.in'),0o644)
    files[config/'systemd/user/hyperterminal-session-persistence.service'] = ((ROOT/'systemd/hyperterminal-session-persistence.service').read_bytes(),0o644)
    files[share/'hyperterminal/README.md'] = ((ROOT/'README.md').read_bytes(),0o644)
    if binary_source:
        for path, (data, mode) in list(files.items()):
            if path.suffix == '.desktop':
                files[path] = (data.replace(b'/hyperterminal-start', b'/hyperterminal'), mode)
    # Preserve existing running sessions while retiring the old socket name on fresh installs.
    legacy = subprocess.run(['tmux','-L','quake-agents','list-sessions'],capture_output=True) if shutil.which('tmux') else None
    if legacy and legacy.returncode == 0 and not os.environ.get('HYPERTERMINAL_TMUX_SOCKET'):
        for path,(data,mode) in list(files.items()):
            if path.parent == bindir:
                data = data.replace(b':-hyperterminal}',b':-quake-agents}')
                data = data.replace(b'#{@hyperterminal_agent}',b'#{@quake_agent}').replace(b'@hyperterminal_agent',b'@quake_agent').replace(b'@hyperterminal_created',b'@quake_created')
                files[path] = (data,mode)
        print('Keeping the legacy tmux socket for existing live sessions.')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = share/'hyperterminal/backups'/stamp
    if args.dry_run:
        for path in files: print(path)
        print('Dry run: no files changed.')
        return
    backup.mkdir(parents=True)
    manifest = []
    for path,(data,mode) in files.items():
        relative = path.relative_to(home)
        existed = path.exists()
        if existed:
            saved = backup/relative
            saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,saved)
        manifest.append({'path':str(relative),'existed':existed})
        path.parent.mkdir(parents=True,exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.'+path.name+'.', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
                os.fchmod(stream.fileno(), mode)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
    (backup/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'HyperTerminal installed. Backup: {backup}')
    if not args.no_activate:
        for command in [['systemctl','--user','daemon-reload'],['systemctl','--user','enable','--now','hyperterminal-session-persistence.service'],['kbuildsycoca6']]:
            if shutil.which(command[0]):
                result = subprocess.run(command,check=False)
                if result.returncode: print('Activation failed: '+' '.join(command))
        print('Log out and back in to reload desktop shortcuts. Existing terminal processes were left running.')

if __name__ == '__main__': main()
