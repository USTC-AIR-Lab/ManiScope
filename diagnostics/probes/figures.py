"""Publication exports: English labels, vector PDF/SVG and 600 dpi PNG."""
import json,gzip,base64,io
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from PIL import Image
from paths import R;O=R/'figures';O.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':10,'axes.labelsize':9,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})
COL={'Pi05':'#2864AD','Motus':'#D46C27'};NAMES={'Pi05':r'$\pi_{0.5}$','Motus':'Motus'}
def save(fig,name):
    for ext in ('png','pdf','svg'):fig.savefig(O/f'{name}.{ext}',dpi=600,bbox_inches='tight',pad_inches=.12)
    fig.savefig(O/f'{name}_preview.png',dpi=140,bbox_inches='tight',pad_inches=.12);plt.close(fig)
def box(ax,x,y,w,h,text,fc='#eef3fa',ec='#8395ac',size=9):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.015',facecolor=fc,edgecolor=ec,linewidth=1));ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=size)
def arrow(ax,a,b,label=None,dashed=False):
    ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',color='#45566e',lw=1.4,linestyle='--' if dashed else '-'))
    if label:ax.text((a[0]+b[0])/2,(a[1]+b[1])/2+.025,label,ha='center',fontsize=8)
def framework():
    fig,ax=plt.subplots(figsize=(9,5.2));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    ax.text(.01,.97,'A capability-based diagnostic framework',fontsize=14,weight='bold')
    box(ax,.02,.69,.19,.14,'Paired inputs\nLanguage, vision\nState and feedback')
    box(ax,.31,.69,.21,.14,'Any policy or agent\nContinuous, discrete\nor tool-based actions')
    box(ax,.62,.69,.15,.14,'Actions\nand tools')
    box(ax,.85,.69,.13,.14,'Environment\nSelection\nExecution')
    arrow(ax,(.21,.76),(.31,.76));arrow(ax,(.52,.76),(.62,.76));arrow(ax,(.77,.76),(.85,.76))
    box(ax,.31,.40,.21,.14,'Future representation\nOptional video readout','#fff3e8','#c5905d')
    arrow(ax,(.415,.69),(.415,.54),'');arrow(ax,(.52,.47),(.69,.69),'Patch internal state',True)
    ax.text(.02,.49,'Output association\nis not mediation',fontsize=9,color='#795430')
    box(ax,.62,.40,.36,.14,'Sham + valid donor + norm controls\nOnly where internals are accessible','#f6f1fa','#a28bb6')
    for x,w,text in [(.02,.29,'Universal behavior readout\nTarget switching and tracking\nSelection vs execution failures'),(.355,.29,'Optional future readout\nGoal-consistent prediction\nReadability and uncertainty'),(.69,.29,'Optional internal readout\nTarget-directed action change\nSeparate from closed-loop benefit')]:box(ax,x,.12,w,.18,text,size=9)
    ax.text(.02,.025,'Unavailable measurements are marked N/A; model families are not assigned a single global modality weight.',fontsize=8)
    save(fig,'01_general_framework')
def paired_design():
    fig,axs=plt.subplots(2,2,figsize=(7,5.3));seed=200000
    for i,target in enumerate(('red','blue')):
        for j,layout in enumerate(('original','swapped')):
            ident=f'pi05_{seed}_{layout}_{target}'
            with gzip.open(R/'runs'/ident/'model_io/0.json.gz','rt') as f:body=json.load(f)
            im=Image.open(io.BytesIO(base64.b64decode(body['request']['observation']['images']['1'])));ax=axs[i,j];ax.imshow(im);ax.axis('off');ax.set_title(('Original layout' if j==0 else 'Red / blue positions exchanged')+'\n'+f'"Pick up the {target} block."',fontsize=10)
    fig.suptitle('Matched language × scene interventions',fontsize=13);fig.tight_layout();save(fig,'02_paired_design')
def outcomes():
    rows=json.loads((R/'analyses/episodes.json').read_text());summary=json.loads((R/'analyses/summary.json').read_text())
    fig,axs=plt.subplots(1,3,figsize=(10.5,3.4),gridspec_kw={'width_ratios':[1,1,1.7]})
    labels=['red','blue','green','none','ambiguous']
    for ax,pol in zip(axs[:2],('Pi05','Motus')):
        a=np.array([[sum(r['target']==t and r['contact_label']==s for r in rows if r['policy']==pol) for s in labels] for t in ('red','blue')]);ax.imshow(a,cmap='Blues',vmin=0,vmax=40,aspect='auto')
        for i in range(2):
            for j in range(5):ax.text(j,i,str(a[i,j]),ha='center',va='center',color='white' if a[i,j]>22 else '#18202b')
        ax.set(xticks=range(5),xticklabels=['Red','Blue','Green','None','Ambig.'],yticks=[0,1],yticklabels=['Red','Blue'],xlabel='First contacted object',ylabel='Requested target',title=NAMES[pol]);ax.tick_params(axis='x',rotation=45)
    keys=['contact_correct','language_switch_pair','layout_tracking_pair','success'];titles=['Target\ncontact','Instruction\npair','Layout\npair','Task\nsuccess']
    ax=axs[2]
    for offset,pol in [(-.18,'Pi05'),(.18,'Motus')]:
        vals=[summary[pol][k]['mean'] for k in keys];lo=[v-summary[pol][k]['ci95'][0] for v,k in zip(vals,keys)];hi=[summary[pol][k]['ci95'][1]-v for v,k in zip(vals,keys)]
        ax.bar(np.arange(4)+offset,vals,.34,color=COL[pol],label=NAMES[pol],yerr=[lo,hi],capsize=3)
    ax.set(xticks=range(4),xticklabels=titles,ylim=(0,1.12),ylabel='Fraction correct',title='Behavioral grounding');ax.legend(frameon=False,ncol=2,loc='upper right');ax.grid(axis='y',alpha=.2)
    fig.suptitle('Target selection and task completion are different measurements',fontsize=12);fig.tight_layout();save(fig,'03_behavioral_grounding')
def factorial():
    d=json.loads((R/'analyses/factorial.json').read_text());fig,axs=plt.subplots(1,3,figsize=(10,3.3));rng=np.random.default_rng(4)
    for ax,pol in zip(axs[:2],('Pi05','Motus')):
        for i,k in enumerate(('action_language_rms','action_visual_rms','action_noise_rms')):
            vals=[r[k] for r in d['rows'] if r['policy']==pol];ax.scatter(i+rng.uniform(-.1,.1,len(vals)),vals,s=14,color=COL[pol],alpha=.65);v=d['summary'][pol][k];ax.errorbar(i,v['mean'],yerr=[[v['mean']-v['ci95'][0]],[v['ci95'][1]-v['mean']]],fmt='D',color='black',capsize=4,markersize=4)
        ax.set(xticks=[0,1,2],xticklabels=['Language','Layout','Noise'],ylabel='First-16-command joint RMS (rad)',title=NAMES[pol]);ax.grid(axis='y',alpha=.2)
    ax=axs[2]
    for i,k in enumerate(('video_language_mae','video_visual_mae','video_noise_mae')):
        vals=[r[k] for r in d['rows'] if r['policy']=='Motus'];ax.scatter(i+rng.uniform(-.1,.1,len(vals)),vals,s=14,color=COL['Motus'],alpha=.65);v=d['summary']['Motus'][k];ax.errorbar(i,v['mean'],yerr=[[v['mean']-v['ci95'][0]],[v['ci95'][1]-v['mean']]],fmt='D',color='black',capsize=4,markersize=4)
    ax.set(xticks=[0,1,2],xticklabels=['Language','Layout','Noise'],ylabel='Forecast RGB MAE [0, 1]',title='Motus future video');ax.grid(axis='y',alpha=.2)
    fig.suptitle('Response magnitude under specified interventions — not global modality importance',fontsize=11);fig.tight_layout();save(fig,'04_factorial_sensitivity')
def future_results():
    rows=json.loads((R/'analyses/future_targets_final.json').read_text());episodes={r['id']:r for r in json.loads((R/'analyses/episodes.json').read_text())}
    fig,axs=plt.subplots(1,2,figsize=(8,3.7));labels=['red','blue','green','none','ambiguous']
    a=np.array([[sum(r['target']==t and r['final_label']==s for r in rows) for s in labels] for t in ('red','blue')]);ax=axs[0];ax.imshow(a,cmap='Oranges',vmin=0,vmax=40,aspect='auto')
    for i in range(2):
        for j in range(5):ax.text(j,i,str(a[i,j]),ha='center',va='center',color='white' if a[i,j]>22 else '#18202b')
    ax.set(xticks=range(5),xticklabels=['Red','Blue','Green','None','Ambig.'],yticks=[0,1],yticklabels=['Red','Blue'],xlabel='Visible forecast approach target',ylabel='Requested target',title='Language → future video');ax.tick_params(axis='x',rotation=35)
    counts=np.zeros((2,2),int);unresolved=0
    for r in rows:
        e=episodes[r['id']]
        if r['final_label'] not in ('red','blue','green') or e['contact_label'] not in ('red','blue','green'):unresolved+=1;continue
        counts[int(r['final_label']==r['target']),int(e['contact_correct'])]+=1
    ax=axs[1];ax.imshow(counts,cmap='Blues',vmin=0,vmax=40)
    for i in range(2):
        for j in range(2):ax.text(j,i,str(counts[i,j]),ha='center',va='center',fontsize=16,color='white' if counts[i,j]>22 else '#18202b')
    ax.set(xticks=[0,1],xticklabels=['Incorrect','Correct'],yticks=[0,1],yticklabels=['Incorrect','Correct'],xlabel='Executed target contact',ylabel='Forecast approach target',title=f'Forecast and contact correctness\nUnresolved: {unresolved} / {len(rows)}')
    fig.suptitle('Agreement with execution does not establish instruction following or mediation',fontsize=11);fig.tight_layout();save(fig,'05_future_and_action')
if __name__=='__main__':
    import sys
    for name in sys.argv[1:] or ['framework']:globals()[name]()
