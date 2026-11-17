"""Paired near-future K/V intervention with per-site K/V norm controls.

Only the action-query output rows are replaced. Video generation remains native.
Token positions are not assumed to contain semantically pure future information.
"""
import os,sys,json,gzip,time,importlib,math
from pathlib import Path
import numpy as np
import torch
from paths import R,REPO
sys.path.insert(0,str(REPO/'policy/Motus'));import serve

class Probe:
    def __init__(self,model):
        self.model=model;self.layers=len(model.video_model.wan_model.blocks);self.site=None;self.mode='baseline';self.counter=0;self.bank={};self.donor={};self.reference={};self.norms=[]
        module=importlib.import_module(type(model.video_model.wan_model.blocks[0].self_attn).__module__);self.flash=module.flash_attention;module.flash_attention=self.attention
        for i,b in enumerate(model.video_model.wan_model.blocks):
            orig=b.self_attn.forward
            def wrapped(*a,_orig=orig,_i=i,**kw):
                if kw.get('action_q') is None:return _orig(*a,**kw)
                self.site=dict(layer=_i,step=self.counter//self.layers,lv=a[0].shape[1],la=kw['action_q'].shape[1],groups=int(a[2][0][0].item()));self.counter+=1
                try:return _orig(*a,**kw)
                finally:self.site=None
            b.self_attn.forward=wrapped
    def reset(self,mode):self.mode=mode;self.site=None;self.counter=0;self.norms=[]
    def attention(self,*a,**kw):
        output=self.flash(*a,**kw);s=self.site
        if s is None:return output
        q,k,v=kw['q'],kw['k'],kw['v'];assert s['groups']==3 and s['lv']==360
        key=f"{s['step']}_{s['layer']}";g=120;spans={'future':(g,2*g),'current':(0,g),'understanding':(s['lv']+s['la'],s['lv']+s['la']+g)}
        if self.mode=='donor':
            self.donor[key]={n:{'k':k[:,lo:hi].detach().cpu().clone(),'v':v[:,lo:hi].detach().cpu().clone()} for n,(lo,hi) in spans.items()};return output
        if self.mode=='baseline':
            # Capture recipient reference norms before any altered action feedback.
            self.bank[key]={n:{'k':k[:,lo:hi].detach().cpu().clone(),'v':v[:,lo:hi].detach().cpu().clone()} for n,(lo,hi) in spans.items()};return output
        if self.mode=='plain':return output
        group='future' if self.mode in ('future','future_half','future_scrambled','sham') else self.mode.split('_')[0]
        lo,hi=spans[group];km=k.clone();vm=v.clone();entry={'site':key,'mode':self.mode}
        for name,source,modified in [('k',k,km),('v',v,vm)]:
            base=source[:,lo:hi];delta=self.donor[key][group][name].to(device=base.device,dtype=base.dtype)-base
            if self.mode=='sham':delta=torch.zeros_like(delta)
            if self.mode=='future_half':delta=delta*.5
            if self.mode.endswith('_matched') or self.mode=='future_scrambled':
                # Match norm of native donor-minus-recipient future perturbation,
                # computed before intervention feedback, independently for K and V.
                reference=self.reference[key][name]
                if self.mode=='future_scrambled':delta=torch.roll(delta,shifts=1,dims=-1)
                norm=delta.float().norm();delta=delta*(reference/(norm+1e-12))
            modified[:,lo:hi]=base+delta
            entry[name+'_applied_delta_norm']=float((modified[:,lo:hi].float()-base.float()).norm());entry[name+'_delta_norm']=float(delta.float().norm());entry[name+'_reference_future_norm']=self.reference[key][name]
        self.norms.append(entry)
        patched=self.flash(*a,**dict(kw,k=km,v=vm));result=output.clone();result[:,s['lv']:s['lv']+s['la']]=patched[:,s['lv']:s['lv']+s['la']];return result

def main():
    lane=int(sys.argv[1]);seeds=list(range(200000+lane,200020,4));out=R/'internal_norm_audit';out.mkdir(exist_ok=True)
    policy=serve.mt.get_model({'ckpt_setting':serve.CKPT,'wan_path':serve.WAN,'vlm_path':serve.VLM,'log_dir':str(R/'logs'/f'probe_{lane}'),'task_name':'directional_probe'});policy.save_images=False
    probe=Probe(policy.model);original=policy.model.inference_step;frames={}
    def deterministic(*a,**kw):
        torch.manual_seed(17);torch.cuda.manual_seed_all(17);ret=original(*a,**kw)
        if probe.mode in ('baseline','donor'):frames[probe.mode]=ret[0].detach().float().cpu().numpy().astype(np.float16)
        return ret
    policy.model.inference_step=deterministic
    for seed in seeds:
        for target in ('red','blue'):
            ident=f'motus_{seed}_original_{target}';dest=out/ident
            while not (R/'runs'/ident/'result.json').exists():
                if (R/'runs'/ident/'error.txt').exists():raise RuntimeError('Primary run failed: '+ident)
                time.sleep(15)
            if (dest/'report.json').exists():continue
            dest.mkdir(exist_ok=False)
            with gzip.open(R/'runs'/ident/'model_io/0.json.gz','rt') as f:io=json.load(f)
            obs=io['request']['observation'];observation={'observation':{n:{'rgb':serve.decode_img(obs['images'][str(i+1)])} for i,n in enumerate(('head_camera','left_camera','right_camera'))},'joint_action':{'vector':np.asarray(obs['state'],np.float32)}}
            donor_target='blue' if target=='red' else 'red';donor_prompt=f'Pick up the {donor_target} block.'
            actions={};norms={};t0=time.time();frames.clear();probe.bank={};probe.donor={}
            def infer(mode,prompt):
                probe.reset(mode);serve.mt.reset_model(policy);policy.set_instruction(prompt);policy.update_obs(observation);a=np.asarray(policy.get_action(),np.float32);norms[mode]=list(probe.norms);return a
            actions['baseline']=infer('baseline',obs['prompt']);replay=float(np.max(np.abs(actions['baseline']-np.asarray(io['response']['actions']))));assert replay<=1e-6,(ident,replay)
            actions['donor']=infer('donor',donor_prompt)
            probe.reference={k:{name:float((probe.donor[k]['future'][name].float()-probe.bank[k]['future'][name].float()).norm()) for name in ('k','v')} for k in probe.bank}
            for mode in ('sham','future_matched','current_matched','understanding_matched','future_scrambled'):
                actions[mode]=infer(mode,obs['prompt'])
                if mode=='sham':assert np.max(np.abs(actions['sham']-actions['baseline']))<=1e-6
            jidx=[0,1,2,3,4,5,7,8,9,10,11,12];d=(actions['donor']-actions['baseline'])[:,jidx].ravel();den=float(d@d)
            metrics={}
            for mode,a in actions.items():
                delta=(a-actions['baseline'])[:,jidx].ravel();metrics[mode]=dict(joint_rms=float(np.sqrt(np.mean(delta**2))),projection_on_donor_direction=float(delta@d/den) if den>1e-12 else None,cosine_to_donor=float(delta@d/(np.linalg.norm(delta)*np.linalg.norm(d))) if np.linalg.norm(delta)*np.linalg.norm(d)>1e-12 else None)
            np.savez_compressed(dest/'actions.npz',**actions);np.savez_compressed(dest/'futures.npz',**frames)
            (dest/'norms.json').write_text(json.dumps(norms));report=dict(id=ident,seed=seed,target=target,donor_target=donor_target,replay_max_abs=replay,sham_max_abs=float(np.max(np.abs(actions['sham']-actions['baseline']))),metrics=metrics,seconds=time.time()-t0,site_count=len(probe.reference))
            (dest/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':main()
