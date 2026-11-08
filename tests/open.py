#!/usr/bin/env python3
"""Isolated checks for the Dolphin folder opener: parent detection, route choice, ledger."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
def run(args,env,check=True):
    result=subprocess.run(args,env=env,check=False,capture_output=True,text=True)
    if check and result.returncode: raise AssertionError(f'{args} failed ({result.returncode}): {result.stderr}')
    return result.stdout.strip()
def plan(env,home,label,directory):
    return dict(line.split('=',1) for line in run([str(home/'.local/bin/hyperterminal-open'),'--plan',label,str(directory)],env).splitlines())
with tempfile.TemporaryDirectory(prefix='hyperterminal-open-') as temp:
    home=Path(temp)
    env=os.environ.copy()
    for key in ['XDG_CONFIG_HOME','XDG_DATA_HOME','CLAUDE_CONFIG_DIR','TMUX','TMUX_PANE','HYPERTERMINAL_STATE_ROOT','HYPERTERMINAL_TMUX_CONFIG','HYPERTERMINAL_OPEN_DECISION','HYPERTERMINAL_OPEN_PRESENT']:
        env.pop(key,None)
    testpath=home/'test-tools'
    testpath.mkdir()
    for binary in ['bash','sh','python3','tmux','mkdir','chmod','base64','mktemp','mv','rm','date','unlink','sed','flock','wc','ls','grep','awk','sort','tr','realpath','true']:
        found=shutil.which(binary)
        if found: (testpath/binary).symlink_to(found)
    env.update(HOME=str(home),PATH=str(testpath),HYPERTERMINAL_TMUX_SOCKET='hyperterminal-open-'+str(os.getpid()),
               HYPERTERMINAL_PROJECT_REGISTRY=str(home/'registry.json'))
    run(['python3',str(ROOT/'install.py'),'--no-activate'],env)
    menu=home/'.local/share/kio/servicemenus/hyperterminal-activities.desktop'
    assert menu.exists() and os.access(menu,os.X_OK) and menu.read_text().count('[Desktop Action ')==5
    assert '@BIN_DIR@' not in menu.read_text() and 'X-KDE-Submenu=Activities' in menu.read_text()
    opener=home/'.local/bin/hyperterminal-open'
    tool=home/'.local/bin/hyperterminal-session'
    runner=home/'.local/bin/hyperterminal-agent-runner'
    runner.write_text('#!/usr/bin/env bash\nexec bash --noprofile --norc\n'); runner.chmod(0o755)
    claude=home/'.local/bin/claude'
    claude.write_text('#!/usr/bin/env bash\nexec bash --noprofile --norc\n'); claude.chmod(0o755)
    # Folder tree: git project with a nested folder, a registry project, and a loose folder.
    project=home/'work/gitproj'; (project/'.git').mkdir(parents=True); nested=project/'src/deep'; nested.mkdir(parents=True)
    registered=home/'work/regproj'; child=registered/'docs'; child.mkdir(parents=True)
    loose=home/'work/loose'; loose.mkdir()
    (home/'registry.json').write_text(json.dumps([{'name':'regproj','path':str(registered),'mine':True}]))
    # Unknown labels and files are rejected; option-like labels never reach the catalog.
    assert subprocess.run([str(opener),'--plan','--help',str(loose)],env=env,capture_output=True).returncode!=0
    assert subprocess.run([str(opener),'--plan','codex-power',str(home/'registry.json')],env=env,capture_output=True).returncode!=0
    p=plan(env,home,'ansr-claude-power',nested)
    assert p['agent']=='claude' and p['parent']==str(project) and p['parent_reason']=='git' and p['route']=='new' and p['parent_route']=='new', p
    p=plan(env,home,'ansr-claude-power',child)
    assert p['parent']==str(registered) and p['parent_reason']=='registry', p
    p=plan(env,home,'ansr-claude-power',project)
    assert p['parent']=='-' and p['route']=='new', p
    p=plan(env,home,'ansr-claude-power',loose)
    assert p['parent']=='-' and p['route']=='new', p
    tmux=['tmux','-L',env['HYPERTERMINAL_TMUX_SOCKET']]
    try:
        # A running record in the folder is reused; it also marks the folder as a project for children.
        name=run([str(tool),'create','claude',str(loose)],env)
        p=plan(env,home,'ansr-claude-power',loose)
        assert p['route']=='running' and p['target']==name, p
        sub=loose/'sub'; sub.mkdir()
        p=plan(env,home,'ansr-claude-power',sub)
        assert p['parent']==str(loose) and p['parent_reason']=='session' and p['parent_route']=='running', p
        assert run([str(tool),'list-records'],env).split('\t')[:2]==[name,'1']
        # queue-tab places the session ahead of pending entries without duplicating it.
        queue=home/'.local/state/hyperterminal/tab-restore.queue'
        queue.write_text('other-1\n'+name+'\n')
        run([str(tool),'queue-tab',name],env)
        assert queue.read_text()==name+'\nother-1\n'
        assert subprocess.run([str(tool),'queue-tab','missing-1'],env=env,capture_output=True).returncode!=0
        queue.unlink()
        # Dormant record after shutdown: restored through resume-saved.
        run([str(tool),'prepare-shutdown'],env)
        run(tmux+['kill-server'],env)
        time.sleep(.15)
        p=plan(env,home,'ansr-claude-power',loose)
        assert p['route']=='saved' and p['target']==name, p
        # Native history in a folder wins over a dormant record and over new.
        history=home/'.claude/projects/gitproj/conv-1.jsonl'; history.parent.mkdir(parents=True)
        history.write_text(json.dumps({'sessionId':'conv-1','cwd':str(project)})+'\n')
        p=plan(env,home,'ansr-claude-power',project)
        assert p['route']=='history' and p['target']=='conv-1', p
        # Headless open. Parent decision resumes the parent's native history; cancel starts nothing;
        # self creates a new session in the child, which then counts as its own workspace (no prompt).
        env_open=dict(env,HYPERTERMINAL_OPEN_DECISION='parent',HYPERTERMINAL_OPEN_PRESENT='none')
        resumed=run([str(opener),'ansr-claude-power',str(nested)],env_open)
        state=home/'.local/state/hyperterminal/sessions'/f'{resumed}.session'
        assert 'conversation_id=conv-1' in state.read_text()
        assert run([str(opener),'ansr-claude-power',str(nested)],env_open)==resumed
        env_open['HYPERTERMINAL_OPEN_DECISION']='cancel'
        assert run([str(opener),'ansr-claude-power',str(nested)],env_open)==''
        env_open['HYPERTERMINAL_OPEN_DECISION']='self'
        created=run([str(opener),'ansr-claude-power',str(nested)],env_open)
        assert created!=resumed and created.startswith('claude-') and created in run([str(tool),'list'],env)
        p=plan(env,home,'ansr-claude-power',nested)
        assert p['parent']=='-' and p['route']=='running' and p['target']==created, p
        env_open['HYPERTERMINAL_OPEN_DECISION']='parent'
        assert run([str(opener),'ansr-claude-power',str(nested)],env_open)==created
        # Missing agent is ledgered, never started.
        assert subprocess.run([str(opener),'codex-power',str(loose)],env=env_open,capture_output=True).returncode!=0
        ledger=(home/'.local/state/hyperterminal/open.ledger').read_text().splitlines()
        assert len(ledger)==6 and all(len(row.split('\t'))==8 for row in ledger)
        routes=[row.split('\t')[5] for row in ledger]
        assert routes==['history','running','-','new','running','-'], routes
        stats=run([str(opener),'--stats'],env)
        assert 'opens=6' in stats and 'decision.cancel=1' in stats and 'outcome.error:agent-missing=1' in stats and 'route.history=1' in stats, stats
    finally:
        subprocess.run(tmux+['kill-server'],env=env,capture_output=True)
print('Folder opener verified: service menu, parent detection, route order, headless open, ledger and stats.')
