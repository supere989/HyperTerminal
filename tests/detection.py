#!/usr/bin/env python3
"""Isolated agent discovery and exact-conversation persistence regression checks."""
import base64
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
def run(args,env):
    return subprocess.run(args,env=env,check=True,capture_output=True,text=True).stdout.strip()

def wait_log(path):
    for _ in range(60):
        if path.exists(): return path.read_bytes().split(b'\0')[:-1]
        time.sleep(.05)
    raise AssertionError('Agent runner did not execute')

with tempfile.TemporaryDirectory(prefix='hyperterminal-detection-') as temp:
    home=Path(temp)
    env=os.environ.copy()
    for key in ['XDG_CONFIG_HOME','XDG_DATA_HOME','CODEX_HOME','CLAUDE_CONFIG_DIR','TMUX','TMUX_PANE','HYPERTERMINAL_STATE_ROOT','HYPERTERMINAL_TMUX_CONFIG']:
        env.pop(key,None)
    testpath=home/'test-tools'
    testpath.mkdir()
    for binary in ['bash','sh','python3','tmux','fish','mkdir','chmod','base64','mktemp','mv','rm','date','unlink','sed','flock','wc','sleep','true']:
        found=shutil.which(binary)
        if found: (testpath/binary).symlink_to(found)
    env.update(HOME=str(home),PATH=str(testpath),HYPERTERMINAL_TMUX_SOCKET='hyperterminal-detection-'+str(os.getpid()))
    run(['python3',str(ROOT/'install.py'),'--no-activate'],env)
    catalog=home/'.local/bin/hyperterminal-catalog'
    # No agents installed: new-agent actions are absent; shell remains selectable.
    assert run([str(catalog),'rows'],env)==''
    agents={'codex':'.local/bin','claude':'.local/bin','grok':'.grok/bin','kimi':'.kimi-code/bin','agy':'.local/bin','opencode':'.opencode/bin'}
    for name,directory in agents.items():
        binary=home/directory/name
        binary.parent.mkdir(parents=True,exist_ok=True)
        binary.write_text('#!/usr/bin/env bash\nprintf "%s\\0" "$@" >"$HOME/agent-argv"\nexec bash --noprofile --norc\n')
        binary.chmod(0o755)
    # Native OpenCode listing is JSON, not a transcript or shell command.
    oc=home/'.opencode/bin/opencode'
    oc.write_text('#!/usr/bin/env bash\nif [[ "${1:-}" == session ]]; then printf \'[{"id":"ses_fixture","directory":"/tmp","title":"fixture","updated":1000}]\'; else exec bash --noprofile --norc; fi\n')
    listing=run([str(catalog),'list'],env)
    assert {line.split('\t')[0] for line in listing.splitlines()}==set(agents)
    rows=run([str(catalog),'rows'],env)
    assert 'new|opencode' in rows and 'picker|codex' in rows and 'latest|agy' in rows
    # Metadata-only fixtures; malformed and sidechain sessions must be excluded.
    project=home/'project'
    project.mkdir()
    codex=home/'.codex/sessions/2026/10/06/fixture.jsonl'
    codex.parent.mkdir(parents=True)
    codex.write_text(json.dumps({'type':'session_meta','payload':{'id':'codex-fixture','cwd':str(project),'source':'cli'}})+'\n')
    bad=codex.with_name('bad.jsonl');bad.write_text('broken')
    claude=home/'.claude/projects/project/claude-fixture.jsonl'
    claude.parent.mkdir(parents=True)
    claude.write_text(json.dumps({'sessionId':'claude-fixture','cwd':str(project),'isSidechain':False})+'\n')
    side=claude.with_name('side.jsonl');side.write_text(json.dumps({'sessionId':'side','cwd':str(project),'isSidechain':True})+'\n')
    grok=home/'.grok/sessions'/str(project).replace('/','%2F')/'grok-fixture'
    grok.mkdir(parents=True)
    kimi=home/'.kimi-code/sessions/workspace/session_kimi-fixture/state.json'
    kimi.parent.mkdir(parents=True)
    kimi.write_text(json.dumps({'id':'kimi-fixture','cwd':str(project)}))
    history=json.loads(run([str(catalog),'history'],env))
    assert {row['id'] for row in history}=={'codex-fixture','claude-fixture','grok-fixture','kimi-fixture','ses_fixture'}
    for agent,expected in [('codex',['resume','codex-fixture']),('claude',['--resume','codex-fixture']),('grok',['--resume','codex-fixture']),('kimi',['--session','codex-fixture']),('agy',['--conversation','codex-fixture']),('opencode',['--session','codex-fixture'])]:
        result=subprocess.run([str(catalog),'command',agent,'--mode','id','--id','codex-fixture'],env=env,check=True,capture_output=True)
        argv=result.stdout.decode().strip('\0').split('\0')
        assert argv[-2:]==expected
    assert subprocess.run([str(catalog),'command','codex','--mode','id','--id','$(touch bad)'],env=env,capture_output=True).returncode!=0
    tool=home/'.local/bin/hyperterminal-session'
    tmux=['tmux','-L',env['HYPERTERMINAL_TMUX_SOCKET']]
    log=home/'agent-argv'
    try:
        name=run([str(tool),'resume-conversation','codex','codex-fixture',str(project)],env)
        assert wait_log(log)[-2:]==[b'resume',b'codex-fixture']
        # Reselecting the same conversation must reuse the existing process.
        pid=run(tmux+['display-message','-p','-t',name,'#{pane_pid}'],env)
        assert run([str(tool),'resume-conversation','codex','codex-fixture',str(project)],env)==name
        assert run(tmux+['display-message','-p','-t',name,'#{pane_pid}'],env)==pid
        run([str(tool),'snapshot'],env)
        state=home/'.local/state/hyperterminal/sessions'/f'{name}.session'
        assert 'conversation_id=codex-fixture' in state.read_text()
        run([str(tool),'prepare-shutdown'],env)
        before=state.read_bytes()
        run(tmux+['kill-server'],env)
        time.sleep(.15)
        assert name in run([str(tool),'list-saved'],env)
        # Removed agent: restoration defers, preserves exact record, and never launches a new conversation.
        binary=home/'.local/bin/codex'; binary.rename(binary.with_name('codex-disabled'))
        assert run([str(tool),'restore'],env)=='restored=0'
        assert state.read_bytes()==before
        binary.with_name('codex-disabled').rename(binary)
        moved=home/'project-away'
        project.rename(moved)
        assert run([str(tool),'restore'],env)=='restored=0'
        assert state.read_bytes()==before
        moved.rename(project)
        log.unlink()
        assert run([str(tool),'resume-saved',name],env)==name
        assert wait_log(log)[-2:]==[b'resume',b'codex-fixture']
        assert 'conversation_id=codex-fixture' in state.read_text()
        # Restoring another record must preserve an already pending tab queue.
        queue=home/'.local/state/hyperterminal/tab-restore.queue'
        queue.write_text(name+'\n')
        # Legacy v1 shell records remain restorable and do not require migration.
        legacy=state.with_name('legacy-shell.session')
        legacy.write_text('version=1\nagent=shell\ndirectory_b64='+base64.b64encode(str(project).encode()).decode()+'\n')
        assert run([str(tool),'restore'],env)=='restored=1'
        assert run([str(tool),'claim-tab'],env)==name
        assert run([str(tool),'claim-tab'],env)=='legacy-shell'
        assert run([str(tool),'resume-saved','legacy-shell'],env)=='legacy-shell' 
        # New sessions must not reuse dormant names and overwrite their saved identity.
        run([str(tool),'prepare-shutdown'],env)
        run(tmux+['kill-server'],env)
        time.sleep(.15)
        previous=state.read_bytes()
        fresh=run([str(tool),'create','codex',str(project)],env)
        assert fresh!=name and state.read_bytes()==previous
    finally:
        subprocess.run(tmux+['kill-server'],env=env,capture_output=True)
print('Agent detection verified: discovery, native history, exact resume argv, process reuse, snapshots, missing-agent recovery, legacy records.')
