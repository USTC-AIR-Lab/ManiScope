"""Isolated paired color-grounding experiment; original benchmark is read-only."""
import os,sys,json,time,base64,gzip,hashlib,traceback,random
from pathlib import Path
import numpy as np
import yaml,requests,cv2

from paths import R as ROOT,REPO as WORK
sys.path[:0]=[str(WORK),str(WORK/'script')]
os.chdir(WORK)
from envs.attr_color_block_3way import attr_color_block_3way
from envs._placement_judge import world_bounds
from pilot_telemetry import Trace,plain

def configuration():
    args=yaml.safe_load((WORK/'task_config/demo_clean.yml').read_text())
    em=yaml.safe_load((WORK/'task_config/_embodiment_config.yml').read_text())
    f=em['aloha-agilex']['file_path']
    cfg=yaml.safe_load((Path(f)/'config.yml').read_text())
    args.update(task_name='attr_color_block_3way',task_config='demo_clean',eval_mode=True,
        left_robot_file=f,right_robot_file=f,left_embodiment_config=cfg,right_embodiment_config=cfg,
        dual_arm_embodied=True,eval_video_log=False,eval_video_save_dir=None,save_data=False,
        save_path=str(ROOT/'scratch'),render_freq=0,policy_name='paired_diagnostic')
    cam=yaml.safe_load((WORK/'task_config/_camera_config.yml').read_text())[args['camera']['head_camera_type']]
    args.update(head_camera_h=cam['h'],head_camera_w=cam['w'])
    return args

def main():
    job=json.loads(Path(sys.argv[1]).read_text());dest=ROOT/'runs'/job['id'];dest.mkdir(parents=True,exist_ok=False)
    (dest/'job.json').write_text(json.dumps(job,indent=2))
    t0=time.time();env=attr_color_block_3way();trace=None;video=None
    try:
        random.seed(job['seed']);env.setup_demo(now_ep_num=0,seed=job['seed'],is_test=True,**configuration())
        if job['layout']=='swapped':
            a,b=env._actors['target'],env._actors['d2'];pa,pb=a.get_pose(),b.get_pose()
            a.actor.set_pose(pb);b.actor.set_pose(pa)
        env.TARGET={'red':'target','blue':'d2'}[job['target']]
        env._p0={k:np.asarray(v.get_pose().p).copy() for k,v in env._actors.items()}
        env._bottom0={k:float(world_bounds(v)[0][2]) for k,v in env._actors.items()}
        env._maxdisp={k:0. for k in env._actors};env._maxz={k:float(p[2]) for k,p in env._p0.items()}
        env.step_lim=job['horizon'];instruction=f"Pick up the {job['target']} block."
        env.set_instruction(instruction=instruction);env.get_instruction=lambda:instruction
        trace=Trace(env,str(dest/'telemetry'),'attr_color_block_3way',job['policy'],job['seed'],instruction)
        def frame(rgb):pass
        env._pilot_frame=frame
        obs=env.get_obs();heads=[];decision=0;initial_hash={}
        for name,val in obs['observation'].items():
            if 'rgb' in val:initial_hash[name]=hashlib.sha256(np.asarray(val['rgb']).tobytes()).hexdigest()
        (dest/'initial.json').write_text(json.dumps(plain(dict(image_sha256=initial_hash,snapshot=trace.snapshot(),positions=env._p0)),indent=2))
        if job.get('setup_only'):
            trace.decision_before(obs);trace.close(False);trace=None
            (dest/'result.json').write_text(json.dumps(dict(status='setup_verified',seconds=time.time()-t0)))
            return
        requests.post(job['url']+'/v1/reset',timeout=30).raise_for_status()
        video=cv2.VideoWriter(str(dest/'execution.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),10,(320,240))
        while env.take_action_cnt<env.step_lim and not env.eval_success:
            trace.decision_before(obs)
            images={str(i+1):base64.b64encode(cv2.imencode('.png',cv2.cvtColor(obs['observation'][name]['rgb'],cv2.COLOR_RGB2BGR))[1]).decode() for i,name in enumerate(('head_camera','left_camera','right_camera'))}
            body=dict(observation=dict(images=images,state=np.asarray(obs['joint_action']['vector']).tolist(),prompt=instruction),
                diagnostic_rng_seed=job.get('noise_seed',17)+decision,save_id=job['id'],decision=decision,
                intervention=job.get('intervention','baseline'))
            reply=requests.post(job['url']+'/v1/infer',json=body,timeout=600);reply.raise_for_status();response=reply.json()
            chunk=np.asarray(response['actions'],dtype=float);assert chunk.ndim==2 and chunk.shape[1]==14 and np.isfinite(chunk).all()
            io=dest/'model_io';io.mkdir(exist_ok=True)
            with gzip.open(io/f'{decision}.json.gz','wt') as f:json.dump(dict(request=body,response=response),f)
            for action in chunk:
                video.write(cv2.cvtColor(obs['observation']['head_camera']['rgb'],cv2.COLOR_RGB2BGR))
                env.take_action(action,action_type='qpos')
                obs=env.get_obs()
                if env.eval_success or env.take_action_cnt>=env.step_lim:break
            trace.decision_after();decision+=1
        trace.close(env.eval_success);trace=None
        result=dict(status='complete',success=bool(env.eval_success),actions=int(env.take_action_cnt),decisions=decision,seconds=time.time()-t0)
        (dest/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    except Exception:
        (dest/'error.txt').write_text(traceback.format_exc());raise
    finally:
        if video:video.release()
        if trace:
            try:trace.close(False,feedback={'infrastructure_error':True})
            except Exception:pass
        try:env.close_env()
        except Exception:pass
if __name__=='__main__':main()
