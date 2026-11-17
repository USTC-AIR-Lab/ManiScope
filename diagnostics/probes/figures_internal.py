from figures import *
d=json.loads((R/'analyses/internal_summary.json').read_text())
modes=['donor','future','future_half','future_matched','current_matched','understanding_matched','future_scrambled','sham']
names=['Full prompt change','Future replacement','Future half dose','Future matched','Current matched','Understanding matched','Scrambled future','Sham']
fig,axs=plt.subplots(2,2,figsize=(10.5,7.2),layout='constrained')
for ax,key,scale,title,xlabel in [(axs[0,0],'joint_rms',1,'A  Action response','Joint RMS (rad)'),(axs[0,1],'target_directed_shift_m',1000,'B  Requested-goal direction','Change toward requested donor goal (mm)')]:
 for i,m in enumerate(modes):
  v=d['summary']['all'][m]['metrics'][key];y=v['mean']*scale;lo,hi=np.array(v['ci95'])*scale
  ax.errorbar(y,i,xerr=[[y-lo],[hi-y]],fmt='o',color='#2864AD' if m.startswith('future') else '#777777',capsize=3,markersize=4)
 ax.set(yticks=range(len(modes)),yticklabels=names,xlabel=xlabel,title=title);ax.invert_yaxis();ax.axvline(0,color='black',lw=.7);ax.grid(axis='x',alpha=.2)
ax=axs[1,0];mm=['future_matched','current_matched','understanding_matched','future_scrambled']
for i,m in enumerate(mm):
 v=[x['fraction_within_10percent'] for x in d['norm_audit'] if x['mode']==m]
 ax.bar(i,100*np.mean(v),color=['#2864AD','#888888','#888888','#b78650'][i]);ax.text(i,100*np.mean(v)+1,f'{100*np.mean(v):.2f}%',ha='center',fontsize=8)
ax.set(xticks=range(4),xticklabels=['Future','Current','Understanding','Scrambled'],ylim=(0,112),ylabel='Sites within 10% of reference norm (%)',title='C  Actual BF16 perturbation audit');ax.tick_params(axis='x',labelsize=8)
ax=axs[1,1];ax.axis('off')
x=d['summary']['represented_contrast']['future'];v=x['metrics']['represented_target_shift_m']['mean']*1000
ax.text(0,1,'D  Is the forecast target actually different?',fontsize=10,va='top')
ax.text(0,.82,f"80 paired intervention states\nValid donor forecasts: {d['summary']['valid_donor']['future']['n_states']} / 80\nReadable different-target contrasts: {x['n_states']} / 80\nIndependent scenes in this subset: {x['n_scenes']}",fontsize=10,va='top',linespacing=1.7)
ax.text(0,.36,f'Future replacement: {v:+.2f} mm in that subset\nDescriptive only; no population interval.\nCommanded kinematics, not executed success.',fontsize=9,va='top',linespacing=1.6)
fig.suptitle('Internal computation changes do not establish successful semantic transfer',fontsize=12)
save(fig,'06_directional_interventions')
