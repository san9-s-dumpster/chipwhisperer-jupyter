"""Plots with explicit units and primary/secondary distinctions."""
import matplotlib.pyplot as plt
import numpy as np
from analysis.distinguisher import cohort_arrays


def survey_plot(record, cycle_markers=None, core_hz=None, roi=None):
    hz = record.metadata['adc_frequency_hz']
    start = record.metadata['sample_window_start']
    t = (start+np.arange(len(record.wave)))/hz*1e3
    fig, ax = plt.subplots(figsize=(12,3))
    stride = max(1,len(t)//20000)
    ax.plot(t[::stride],record.wave[::stride],lw=.5)
    if cycle_markers:
        for key,color in [('first_squeeze_return','tab:red'),('second_squeeze_start','tab:orange')]:
            ax.axvline(cycle_markers[key]/core_hz*1e3,color=color,label=key+' (calibration estimate)')
    if roi:
        ax.axvspan(roi[0]/hz*1e3,roi[1]/hz*1e3,alpha=.2,color='green',label='new capture window')
    ax.set(xlabel='Time since trigger (ms)',ylabel='Raw ADC codes',title='Complete sampler survey; decimated for display only')
    if cycle_markers or roi: ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def development_plot(records,plan,selection,frozen=None):
    X,y,_,_,sig = cohort_arrays(records,plan,'development')
    a,b = selection['best_window']
    t = (sig['offset']+np.arange(X.shape[1]))/sig['adc_frequency_hz']*1e6
    fig,axes = plt.subplots(2,1,figsize=(12,6))
    for label,name in [(0,'Rejected first candidate'),(1,'Accepted first candidate')]:
        axes[0].plot(t,X[y==label].mean(0),label=name,lw=.8)
    axes[0].axvspan(t[a],t[b-1],color='grey',alpha=.25,label='selected ROI')
    axes[0].set(ylabel='Mean ADC codes',title='Development data only — selected CV score is optimistic')
    axes[0].legend()
    score = np.abs(X[y==0].mean(0)-X[y==1].mean(0))/np.sqrt(X[y==0].var(0)/(y==0).sum()+X[y==1].var(0)/(y==1).sum()+1e-12)
    axes[1].plot(t,score,lw=.8)
    if frozen:
        idx = a+np.array(frozen['models']['single_trace']['power']['indices'])
        axes[1].scatter(t[idx],score[idx],c='red',s=15,label='frozen points of interest')
        axes[1].legend()
    axes[1].set(xlabel='Time since trigger (µs)',ylabel='Absolute Welch score')
    fig.tight_layout()
    return fig


def evaluation_plot(report):
    results = report['results']['single_trace']
    fig,axes = plt.subplots(1,2,figsize=(11,4))
    names = ['power','timing','shuffled_labels']
    means = [results[n]['balanced_accuracy'] for n in names]
    intervals = np.array([results[n]['balanced_accuracy_95ci'] for n in names])
    axes[0].errorbar(np.arange(3),means,yerr=[means-intervals[:,0],intervals[:,1]-means],fmt='o',capsize=5)
    axes[0].axhline(.5,c='grey',ls='--',label='chance / majority baseline')
    axes[0].set(xticks=range(3),xticklabels=['Power','Total timing','Shuffled labels'],ylim=(0,1.03),ylabel='Balanced accuracy; seed bootstrap 95% CI',title='Fresh holdout: one trace per seed')
    axes[0].legend(fontsize=8)
    cm = np.array(results['power']['confusion_matrix_reject_valid'])
    axes[1].imshow(cm,cmap='Blues',vmin=0)
    for i in range(2):
        for j in range(2): axes[1].text(j,i,str(cm[i,j]),ha='center',va='center')
    axes[1].set(xticks=[0,1],yticks=[0,1],xticklabels=['Reject','Accept'],yticklabels=['Reject','Accept'],xlabel='Predicted',ylabel='Actual',title='Frozen power classifier')
    fig.tight_layout()
    return fig
