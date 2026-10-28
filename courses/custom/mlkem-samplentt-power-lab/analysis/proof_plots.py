"""Two compact views of the fixed classifier's fresh physical test."""
import numpy as np
import matplotlib.pyplot as plt


def result_figure(X,y,scores,preset,adc_hz):
    fig,axes=plt.subplots(1,2,figsize=(11,3.3))
    colors=['#b54439','#2568a5'];labels=['Reject','Accept']
    time=(preset['offset']+np.arange(X.shape[1]))/adc_hz*1e6
    for label in (0,1):
        axes[0].plot(time,X[y==label].mean(0),color=colors[label],label=labels[label],lw=.8)
        axes[1].hist(scores['power'][y==label],bins=20,alpha=.65,color=colors[label],label=labels[label])
    axes[0].set(xlabel='Time since trigger (µs)',ylabel='Mean ADC codes',title='Fresh-test power waveforms')
    axes[1].axvline(0,color='black',ls='--',label='Frozen threshold')
    axes[1].set(xlabel='Frozen classifier score',ylabel='Independent test seeds',title='One capture per unseen seed')
    for ax in axes:ax.legend(fontsize=8)
    fig.tight_layout()
    return fig
