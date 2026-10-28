import numpy as np
import matplotlib.pyplot as plt
from .evaluate import mock_seed_segments


def plot_mock_summary(datasets):
    fig,axes=plt.subplots(2,2,figsize=(12,7),constrained_layout=True)
    colors={"variable_time":"#167d9a","fls":"#a14c79"}
    for ax,variant in zip(axes[0],["variable_time","fls"]):
        record=datasets[variant][0]
        ax.plot(record.wave,color=colors[variant],lw=0.6)
        ax.set(title=f"{variant}: synthetic waveform",xlabel="Synthetic sample index",
               ylabel="Arbitrary amplitude")
    ax=axes[1,0]
    for variant,records in datasets.items():
        times=[r.metadata["timing_value"] for r in records]
        ax.hist(times,bins=24,alpha=0.7,label=variant,color=colors[variant])
    ax.set(title="Injected duration distributions",xlabel="Synthetic ADC samples",ylabel="Captures")
    ax.legend()
    X,y,_=mock_seed_segments(datasets["fls"],candidate_index=0)
    ax=axes[1,1]
    for label,color,name in [(0,"#e08a36","Rejected"),(1,"#376c62","Valid")]:
        values=X[y==label]
        mean=values.mean(axis=0)
        sem=values.std(axis=0,ddof=1)/np.sqrt(len(values))
        ax.plot(mean,label=f"{name} (n={len(values)} seeds)",color=color)
        ax.fill_between(np.arange(len(mean)),mean-sem,mean+sem,color=color,alpha=0.2)
    ax.set(title="FLS mock candidate 0: mean ± SEM",xlabel="Sample within mock segment",
           ylabel="Arbitrary amplitude")
    ax.legend(fontsize=8)
    for ax in axes.flat:
        ax.spines[["top","right"]].set_visible(False)
    fig.suptitle("SYNTHETIC PIPELINE CHECK — no hardware leakage measurement",fontsize=13)
    return fig
