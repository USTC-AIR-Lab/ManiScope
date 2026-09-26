"""Regression checks for portability and reproducible benchmark inputs."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import yaml
ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_repository_contract():
    errors, counts = load("validate_repo").validate()
    assert not errors, "\n".join(errors)
    assert counts["scenes"] == 48

def test_missing_or_insufficient_seeds_are_rejected(tmp_path):
    for d in ['envs','description/task_instruction','suite/seeds','task_config']: (tmp_path/d).mkdir(parents=True)
    (tmp_path/'envs/example.py').write_text('')
    (tmp_path/'description/task_instruction/example.json').write_text('{}')
    (tmp_path/'task_config/demo_clean.yml').write_text('{}')
    preflight = load('preflight')
    assert any('missing frozen seeds' in e for e in preflight.validate(['example'],1,'demo_clean',root=tmp_path))
    (tmp_path/'suite/seeds/example.json').write_text(json.dumps({'seeds':[7]}))
    assert any('fewer frozen seeds' in e for e in preflight.validate(['example'],2,'demo_clean',root=tmp_path))
    assert preflight.validate(['example'],1,'demo_clean',root=tmp_path) == []

def test_all_formal_inputs_pass_preflight():
    s = yaml.safe_load((ROOT/'suite/scenes_v2.yaml').read_text())
    tasks=[v['name'] for a in s['axes'].values() for v in a['scenes']]
    assert load('preflight').validate(tasks,100,'demo_clean') == []

def test_frozen_manifest_export_is_non_destructive(tmp_path):
    source = ROOT/'suite/scenes_v2.yaml'; before = source.read_bytes()
    output = tmp_path/'export.yaml'
    subprocess.run([sys.executable,str(ROOT/'suite/gen_yaml.py'),'--output',str(output)],check=True,cwd=ROOT)
    assert yaml.safe_load(output.read_text()) == yaml.safe_load(before)
    result = subprocess.run([sys.executable,str(ROOT/'suite/gen_yaml.py'),'--output',str(source)],capture_output=True)
    assert result.returncode != 0 and source.read_bytes() == before

def test_local_config_does_not_override_explicit_environment(tmp_path):
    config=tmp_path/'config.env'; config.write_text('PORT=1111\nSIM_GPU=6\nCUSTOM_SETTING=example\n')
    import os
    env=dict(os.environ,MANIPSCOPE_CONFIG=str(config),PORT='2222',SIM_GPU='1')
    result=subprocess.run(['bash','-c','source suite/config.sh; printf "%s %s %s" "$PORT" "$SIM_GPU" "$CUSTOM_SETTING"'],cwd=ROOT,env=env,capture_output=True,text=True,check=True)
    assert result.stdout == '2222 1 example'

def test_runner_propagates_failure_and_records_metadata(tmp_path):
    """Exercise the real shell runner with a fake simulator and a loopback service."""
    import os, shutil, socket, threading
    for f in ['suite/run_suite.sh','suite/config.sh','tools/preflight.py','tools/run_metadata.py']:
        p=tmp_path/f; p.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/f,p)
    for folder in ['policy/Fake','assets/objects','assets/embodiments','task_config','description/task_instruction','envs','suite/seeds']:
        (tmp_path/folder).mkdir(parents=True,exist_ok=True)
    (tmp_path/'task_config/demo_clean.yml').write_text('{}')
    (tmp_path/'policy/Fake/deploy_policy.yml').write_text('{}')
    (tmp_path/'suite/scenes_v2.yaml').write_text('axes: {}')
    (tmp_path/'suite/policies.yaml').write_text(yaml.safe_dump({'policies':{'fake':{'policy_name':'Fake','ckpt_setting':'fake','server':'http','port':1,'launch':''}}}))
    for name in ['ok_task','bad_task']:
        (tmp_path/'envs'/f'{name}.py').write_text('')
        (tmp_path/'description/task_instruction'/f'{name}.json').write_text('{}')
        (tmp_path/'suite/seeds'/f'{name}.json').write_text(json.dumps({'seeds':[123]}))
    fake=tmp_path/'fake-python'
    fake.write_text('#!'+sys.executable+'\nimport sys,os,json,pathlib\na=sys.argv; out=pathlib.Path(a[a.index("--eval_output_dir")+1]); (out/"captured.json").write_text(json.dumps({"video":os.environ.get("ROBOTWIN_VIDEO_FIRST_N"),"frozen":os.environ.get("ROBOTWIN_FROZEN_SEEDS")})); sys.exit(7 if "bad_task" in a else 0)\n')
    fake.chmod(0o755)
    # A fake ffmpeg is enough: the runner only checks availability in this test.
    (tmp_path/'ffmpeg').write_text('#!/bin/sh\nexit 0\n');(tmp_path/'ffmpeg').chmod(0o755)
    server=socket.socket(); server.bind(('127.0.0.1',0));server.listen();port=server.getsockname()[1]
    stop=threading.Event();server.settimeout(0.1)
    def serve():
        while not stop.is_set():
            try:c,_=server.accept();c.close()
            except socket.timeout:pass
    worker=threading.Thread(target=serve);worker.start()
    try:
        env=dict(os.environ,AUTO_LAUNCH='0',PORT=str(port),EPISODES='1',RUN_NAME='integration',ROBOTWIN_PYTHON=str(fake),YAML_PY=sys.executable,ROBOTWIN_VIDEO_FIRST_N='3',ROBOTWIN_FROZEN_SEEDS='1',PATH=str(tmp_path)+os.pathsep+os.environ['PATH'],MANIPSCOPE_CONFIG=str(tmp_path/'missing.env'))
        result=subprocess.run(['bash','suite/run_suite.sh','fake','ok_task','bad_task'],cwd=tmp_path,env=env,capture_output=True,text=True,timeout=20)
        assert result.returncode != 0
        captures=list((tmp_path/'eval_result').rglob('captured.json'));assert len(captures)==2
        assert all(json.loads(p.read_text())=={'video':'3','frozen':'1'} for p in captures)
        metadata=list((tmp_path/'eval_result').rglob('_run_metadata.json'));assert len(metadata)==2
        assert all(json.loads(p.read_text())['episodes']==1 for p in metadata)
    finally:
        stop.set();worker.join();server.close()


def test_relocated_assets_are_resolved_without_mutating_input(tmp_path):
    import copy
    spec=importlib.util.spec_from_file_location("asset_paths",ROOT/"envs/robot/asset_paths.py")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    directory=tmp_path/"robot";directory.mkdir();(directory/"urdf").mkdir()
    (directory/"urdf/model.urdf").write_text("<robot/>")
    (directory/"spheres.yml").write_text("{}")
    config={"robot_cfg":{"kinematics":{"urdf_path":"/old/workspace/robot/urdf/model.urdf","collision_spheres":"/old/workspace/robot/spheres.yml","asset_root_path":None}}}
    original=copy.deepcopy(config)
    result=mod.resolve_robot_config(config,directory/"curobo.yml")
    assert config==original
    assert result["robot_cfg"]["kinematics"]["urdf_path"]==str(directory/"urdf/model.urdf")
    assert result["robot_cfg"]["kinematics"]["collision_spheres"]==str(directory/"spheres.yml")


def test_missing_local_asset_is_rejected(tmp_path):
    import pytest
    spec=importlib.util.spec_from_file_location("asset_paths",ROOT/"envs/robot/asset_paths.py")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    with pytest.raises(FileNotFoundError):
        mod.resolve_robot_config({"robot_cfg":{"kinematics":{"urdf_path":"urdf/missing.urdf"}}},tmp_path/"curobo.yml")


def test_generic_personal_path_detection():
    checker = load('validate_repo')
    for prefix in ('/home', '/Users'):
        assert checker.personal_path(prefix + '/example-user/project')
        assert not checker.personal_path(prefix + '/<user>/project')
    assert not checker.personal_path('https://example.invalid/project')
