#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
def run(args,env=None,**kwargs):
    return subprocess.run(args,env=env,check=True,text=True,capture_output=True,**kwargs).stdout.strip()
for p in (ROOT/'bin').iterdir(): run(['bash','-n',str(p)])
for p in (ROOT/'assets').rglob('*.svg'): ET.parse(p)
with tempfile.TemporaryDirectory(prefix='hyperterminal-test-') as temp:
    home=Path(temp)
    env=os.environ.copy()
    for key in ['XDG_CONFIG_HOME','XDG_DATA_HOME','HYPERTERMINAL_STATE_ROOT','HYPERTERMINAL_TMUX_CONFIG','TMUX','TMUX_PANE']: env.pop(key,None)
    env['HOME']=str(home)
    env['HYPERTERMINAL_TMUX_SOCKET']='hyperterminal-test-'+str(os.getpid())
    original=home/'.config/yakuakerc'
    original.parent.mkdir()
    original.write_text('[Unrelated]\nPreserve=yes\n')
    run(['python3',str(ROOT/'install.py'),'--dry-run'],env)
    assert not (home/'.local').exists()
    run(['python3',str(ROOT/'install.py'),'--no-activate'],env)
    assert 'Preserve=yes' in original.read_text()
    assert '@BIN_DIR@' not in (home/'.local/share/konsole/HyperTerminal.profile').read_text()
    backup=next((home/'.local/share/hyperterminal/backups').iterdir())
    assert (backup/'.config/yakuakerc').read_text()=='[Unrelated]\nPreserve=yes\n'
    tool=home/'.local/bin/hyperterminal-session'
    # Test the real manager using a shell-only runner to avoid requiring Fish or agent CLIs.
    runner=home/'.local/bin/hyperterminal-agent-runner'
    runner.write_text('#!/usr/bin/env bash\nexec bash --noprofile --norc\n')
    runner.chmod(0o755)
    tmux=['tmux','-L',env['HYPERTERMINAL_TMUX_SOCKET']]
    try:
        name=run([str(tool),'create','shell',str(home)],env)
        assert 'shell' in run([str(tool),'list'],env)
        run([str(tool),'queue-detached-tabs'],env)
        assert run([str(tool),'queue-count'],env)=='1'
        assert run([str(tool),'claim-tab'],env)==name
        assert run([str(tool),'queue-count'],env)=='0'
        # Empty queues must also succeed under set -e.
        run([str(tool),'queue-detached-tabs'],env)
        run([str(tool),'prepare-shutdown'],env)
        run(tmux+['kill-server'],env)
        time.sleep(.15)
        run([str(tool),'queue-detached-tabs'],env)
        assert run([str(tool),'queue-count'],env)=='0'
        assert run([str(tool),'restore'],env)=='restored=1'
        assert run([str(tool),'claim-tab'],env)==name
        assert run([str(tool),'restore'],env)=='restored=0'
        # Forget is inhibited by the shutdown marker, then allowed after restore.
        state=home/'.local/state/hyperterminal/sessions'/f'{name}.session'
        run([str(tool),'forget',name],env)
        assert not state.exists()
        assert subprocess.run([str(tool),'create','invalid'],env=env,capture_output=True).returncode!=0
    finally:
        subprocess.run(tmux+['kill-server'],env=env,capture_output=True)
    run(['python3',str(ROOT/'restore-install.py'),str(backup)],env)
    assert original.read_text()=='[Unrelated]\nPreserve=yes\n'
    assert not tool.exists()
print('HyperTerminal verification passed: syntax, SVG assets, installer backup/restore, tmux lifecycle and queue.')
