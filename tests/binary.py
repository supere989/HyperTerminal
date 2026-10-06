#!/usr/bin/env python3
"""Exercise the actual binary consent boundary using harmless package-manager fixtures."""
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
BINARY=Path(os.environ.get('HYPERTERMINAL_TEST_BINARY',ROOT/'target/release/hyperterminal'))

def interact(command, env, answer):
    master,slave=pty.openpty()
    proc=subprocess.Popen(command,env=env,stdin=slave,stdout=slave,stderr=slave)
    os.close(slave)
    output=b''; replied=False
    deadline=time.monotonic()+15
    try:
        while time.monotonic()<deadline:
            ready,_,_=select.select([master],[],[],.1)
            if ready:
                try: data=os.read(master,65536)
                except OSError: data=b''
                output+=data
                if b'Proceed? [y/N]' in output and not replied:
                    os.write(master,(answer+'\n').encode());replied=True
            if proc.poll() is not None: break
        if proc.poll() is None:
            proc.kill();raise AssertionError('Consent prompt or installation timed out')
        assert replied,output.decode(errors='replace')
        return proc.wait(),output.decode(errors='replace')
    finally:
        os.close(master)

with tempfile.TemporaryDirectory(prefix='hyperterminal-binary-') as temp:
    home=Path(temp);tools=home/'tools';tools.mkdir()
    env=os.environ.copy()
    for key in ['XDG_CONFIG_HOME','XDG_DATA_HOME','HYPERTERMINAL_TMUX_SOCKET','HYPERTERMINAL_BINARY_SOURCE','DISPLAY','WAYLAND_DISPLAY']:
        env.pop(key,None)
    env.update(HOME=str(home),PATH=str(tools))
    required=['python3','bash','fish','tmux','rg','wl-copy','wl-paste','flock','ps','awk','sed','grep','base64','mktemp','mkdir','chmod','mv','rm','unlink','date','wc','tr','sleep','true']
    for name in required:
        target=shutil.which(name) or shutil.which('true')
        (tools/name).symlink_to(target)
    # Simulate an existing legacy tmux backend: only scripts may be rewritten.
    (tools/'tmux').unlink()
    (tools/'tmux').write_text('#!/usr/bin/env bash\nif [[ "$*" == "-L quake-agents list-sessions" ]]; then exit 0; fi\nexec /usr/bin/tmux "$@"\n')
    (tools/'tmux').chmod(0o755)
    for name in ['yakuake','konsole','qdbus-qt6']:
        (tools/name).symlink_to(shutil.which('true'))
    sudo=tools/'sudo';sudo.write_text('#!/usr/bin/env bash\nexec "$@"\n');sudo.chmod(0o755)
    manager=tools/'apt-get'
    manager.write_text('#!/usr/bin/env bash\nprintf "%s\\0" "$@" >"$HOME/package-call"\nln -s /usr/bin/true "$HOME/tools/fzf"\n')
    # Fixture needs ln; no real package manager or network command can be reached.
    (tools/'ln').symlink_to(shutil.which('ln'));manager.chmod(0o755)
    version=subprocess.run([str(BINARY),'--version'],env=env,check=True,capture_output=True,text=True)
    assert '0.3.0' in version.stdout
    doctor=subprocess.run([str(BINARY),'doctor'],env=env,capture_output=True,text=True)
    assert doctor.returncode==1 and 'MISSING  fzf' in doctor.stdout
    assert not (home/'.local').exists()
    # No interactive UI: do not download, deploy, or interpret piped 'yes' as permission.
    unattended=subprocess.run([str(BINARY),'install','--no-activate'],env=env,input='yes\n',capture_output=True,text=True)
    assert unattended.returncode!=0
    assert not (home/'package-call').exists() and not (home/'.local').exists()
    # Desktop confirmation defaults to the No radio option and checks the returned tag.
    dialog=tools/'kdialog'
    dialog.write_text('#!/usr/bin/env bash\nprintf "%s\\0" "$@" >"$HOME/dialog-call"\nprintf decline\n')
    dialog.chmod(0o755)
    (tools/'pkexec').symlink_to(sudo)
    refused=subprocess.run([str(BINARY),'install','--no-activate'],env=env,capture_output=True,text=True)
    assert refused.returncode!=0
    assert not (home/'package-call').exists() and not (home/'.local').exists()
    dialog_args=(home/'dialog-call').read_bytes().split(b'\0')[:-1]
    assert b'--radiolist' in dialog_args and dialog_args[-6:]==[b'decline', 'No — cancel'.encode(), b'on', b'approve', 'Yes — proceed'.encode(), b'off']
    dialog.unlink();(tools/'pkexec').unlink()
    declined,output=interact([str(BINARY),'install','--no-activate'],env,'')
    assert declined!=0 and 'declined' in output
    assert not (home/'package-call').exists() and not (home/'.local').exists()
    # Failed installer after consent cannot deploy the user runtime.
    manager.write_text('#!/usr/bin/env bash\nprintf failed >"$HOME/package-call"\nexit 42\n')
    failed,output=interact([str(BINARY),'install','--no-activate'],env,'yes')
    assert failed!=0 and 'failed' in output
    assert not (home/'.local').exists()
    # Success exit without providing the missing dependency also blocks deployment.
    manager.write_text('#!/usr/bin/env bash\nexit 0\n')
    failed,output=interact([str(BINARY),'install','--no-activate'],env,'yes')
    assert failed!=0 and 'still unavailable' in output
    assert not (home/'.local').exists()
    # Explicit permission with a successful fixture installer proceeds to deployment.
    manager.write_text('#!/usr/bin/env bash\nprintf "%s\\0" "$@" >"$HOME/package-call"\nln -s /usr/bin/true "$HOME/tools/fzf"\n')
    succeeded,output=interact([str(BINARY),'install','--no-activate'],env,'yes')
    assert succeeded==0,output
    argv=(home/'package-call').read_bytes().split(b'\0')[:-1]
    assert argv==[b'install',b'--yes',b'--',b'fzf']
    installed=home/'.local/bin/hyperterminal'
    assert installed.read_bytes()==BINARY.read_bytes()
    assert '/hyperterminal\n' in (home/'.local/share/applications/org.kde.yakuake.desktop').read_text()
    assert (home/'.local/share/hyperterminal/bundle-version').exists()
    runtime=next((home/'.local/share/hyperterminal/runtime').iterdir())
    assert 'qt_candidates' in (runtime/'install.py').read_text()
    # A second install replaces the executable atomically and backs it up.
    again=subprocess.run([str(installed),'install','--no-activate'],env=env,capture_output=True,text=True)
    assert again.returncode==0,again.stderr
    assert installed.read_bytes()==BINARY.read_bytes()
    assert len(list((home/'.local/share/hyperterminal/backups').iterdir()))==2
print('Binary verified: read-only checks, default-No consent, noninteractive refusal, failed/incomplete installation, approved deployment, atomic executable upgrades.')
