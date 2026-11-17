import os,sys,json,subprocess,time
from pathlib import Path
from paths import R,REPO,TOOLS,B,SIM_PYTHON,python_for
def env(gpu):
    (R/'logs').mkdir(parents=True,exist_ok=True);e=os.environ.copy();e.update(PATHWAYS_ROOT=str(R),CUDA_VISIBLE_DEVICES=str(gpu),PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',
      PI05_CKPT=str(B/'checkpoints/pi05_robotwin2'),PYTHONPATH=str(B/'repos/openpi/src')+':'+str(B/'repos/openpi/packages/openpi-client/src'),
      MOTUS_ROOT=str(B/'repos/Motus'),MOTUS_CKPT=str(B/'checkpoints/motus_robotwin2'),MOTUS_WAN=str(B/'checkpoints/diffsynth/Wan-AI/Wan2.2-TI2V-5B'),MOTUS_VLM=str(B/'checkpoints/Qwen3-VL-2B-Instruct'),
      MPLCONFIGDIR=str(R/'logs/mpl'))
    return e
def launch_service(gpu,kind):
    f=open(R/'logs'/f'service_{gpu}.log','a');e=env(gpu)
    p=subprocess.Popen([python_for(kind),str(TOOLS/'service.py'),kind,str(8200+gpu)],env=e,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    m=dict(gpu=gpu,kind=kind,port=8200+gpu,pid=p.pid,time=time.time());(R/'logs'/f'service_{gpu}.json').write_text(json.dumps(m,indent=2));print(m,flush=True)
if __name__=='__main__':
    for gpu in map(int,sys.argv[1:]):launch_service(gpu,'pi05' if gpu<4 else 'motus')
