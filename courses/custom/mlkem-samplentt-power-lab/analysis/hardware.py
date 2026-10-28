"""Legacy exploratory ROI classifier; not used by the v2 hardware notebook.

Use analysis.distinguisher for frozen, independently acquired final evaluation.
"""
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (balanced_accuracy_score, confusion_matrix,
    precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def seed_roi(records, start, stop, candidate_index=0, bins=32):
    """One averaged waveform per seed; no assumed candidate boundaries."""
    if not records:
        raise ValueError("capture a batch first")
    if not (0 <= start < stop <= min(len(r.wave) for r in records)):
        raise ValueError("ROI must lie inside every recorded trace")
    if not 1 <= bins <= stop-start:
        raise ValueError("ROI must contain at least one sample per feature bin")
    signatures = {(r.truth["variant"],r.truth["x"],r.truth["y"],
                   r.metadata["sample_window_start"],r.metadata["adc_frequency_hz"])
                  for r in records}
    if len(signatures) != 1:
        raise ValueError("analyze one variant, index pair and capture window at a time")
    grouped = {}
    for record in records:
        if not 0 <= candidate_index < len(record.truth["valid"]):
            raise ValueError("candidate index is outside a trace's ground-truth schedule")
        grouped.setdefault(record.truth["seed"],[]).append(record)
    seeds=sorted(grouped)
    waves=np.array([np.mean([r.wave[start:stop] for r in grouped[s]],axis=0) for s in seeds])
    y=np.array([int(grouped[s][0].truth["valid"][candidate_index]) for s in seeds])
    X=np.array([[chunk.mean() for chunk in np.array_split(w,bins)] for w in waves])
    return X,y,seeds,waves


def classify_roi(records, start, stop, candidate_index=0, bins=32, split_seed=123):
    X,y,seeds,_=seed_roi(records,start,stop,candidate_index,bins)
    if len(np.unique(y)) != 2 or np.min(np.bincount(y)) < 4:
        raise ValueError("need at least four distinct seeds in each class; collect more seeds")
    train,test=train_test_split(np.arange(len(y)),test_size=0.3,stratify=y,
                                random_state=split_seed)
    model=make_pipeline(StandardScaler(),LogisticRegression(
        class_weight="balanced",max_iter=1000,random_state=split_seed))
    model.fit(X[train],y[train])
    predicted=model.predict(X[test])
    probability=model.predict_proba(X[test])[:,1]
    dummy=DummyClassifier(strategy="most_frequent").fit(X[train],y[train])
    return {"roi_samples":[start,stop],"feature_bins":bins,
            "candidate_index":candidate_index,"split_seed":split_seed,
            "train_seeds":[seeds[i] for i in train],
            "test_seeds":[seeds[i] for i in test],
            "balanced_accuracy":float(balanced_accuracy_score(y[test],predicted)),
            "precision_valid":float(precision_score(y[test],predicted,zero_division=0)),
            "recall_valid":float(recall_score(y[test],predicted,zero_division=0)),
            "roc_auc":float(roc_auc_score(y[test],probability)),
            "confusion_matrix_reject_valid":confusion_matrix(y[test],predicted,labels=[0,1]).tolist(),
            "majority_balanced_accuracy":float(balanced_accuracy_score(y[test],dummy.predict(X[test]))),
            "interpretation":"Association with candidate validity in a selected ROI; does not localize the comparison or identify the seed."}
