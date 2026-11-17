import os,sys,json,time,logging
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
import numpy as np
import torch
from paths import R,REPO as W
kind=sys.argv[1];port=int(sys.argv[2]);sys.path.insert(0,str(W/'policy'/('Pi05' if kind=='pi05' else 'Motus')))
import serve
if kind=='pi05':
    policy=serve.build_policy()
else:
    policy=serve.mt.get_model({'ckpt_setting':serve.CKPT,'wan_path':serve.WAN,'vlm_path':serve.VLM,'log_dir':str(R/'logs'/f'model_{port}'),'task_name':'pathways'})
    policy.save_images=False
    original=policy.model.inference_step
    captured={}
    def capture(*a,**kw):
        result=original(*a,**kw)
        if captured.get('save'):
            captured['frames']=result[0].detach().float().cpu().numpy().astype(np.float16)
        return result
    policy.model.inference_step=capture

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def send(self,obj,code=200):
        data=json.dumps(obj).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):self.send({'ok':True,'kind':kind})
    def do_POST(self):
        try:
            body=json.loads(self.rfile.read(int(self.headers['Content-Length']))) if int(self.headers.get('Content-Length',0)) else {}
            if self.path=='/v1/reset':
                if kind=='motus':serve.mt.reset_model(policy)
                return self.send({'ok':True})
            obs=body['observation'];seed=int(body['diagnostic_rng_seed']);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
            dest=R/'predictions'/body['save_id']/str(body['decision']);dest.mkdir(parents=True,exist_ok=True)
            torch.save({'cpu_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all()},dest/'rng.pt')
            t0=time.time()
            if kind=='pi05':
                example={'images':{n:serve.decode_img(obs['images'][str(i+1)]) for i,n in enumerate(('cam_high','cam_left_wrist','cam_right_wrist'))},'state':np.asarray(obs['state'],np.float32),'prompt':obs['prompt']}
                actions=np.asarray(policy.infer(example)['actions'])
            else:
                captured.clear();captured['save']=body['decision']==0
                observation={'observation':{n:{'rgb':serve.decode_img(obs['images'][str(i+1)])} for i,n in enumerate(('head_camera','left_camera','right_camera'))},'joint_action':{'vector':np.asarray(obs['state'],np.float32)}}
                policy.set_instruction(obs['prompt']);policy.update_obs(observation);actions=np.asarray(policy.get_action())
                if 'frames' in captured:np.savez_compressed(dest/'future.npz',frames=captured['frames'])
            np.savez_compressed(dest/'actions.npz',actions=actions)
            self.send({'actions':actions.tolist(),'infer_time':time.time()-t0})
        except Exception as e:
            logging.exception('inference failed');self.send({'error':str(e)},500)
print('READY',kind,port,flush=True);HTTPServer(('127.0.0.1',port),Handler).serve_forever()
