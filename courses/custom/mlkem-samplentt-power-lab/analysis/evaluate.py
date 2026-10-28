"""Exploratory mock evaluation with one averaged segment per seed."""
import numpy as np
from scipy.stats import ttest_ind
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (balanced_accuracy_score, confusion_matrix,
    precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def mock_seed_segments(records, candidate_index=0):
    """Mock boundaries only. Hardware requires measured candidate localization.

    Collapse repetitions BEFORE splitting; independent seeds are the unit of
    evaluation. Choose the candidate index before looking at test results.
    """
    if not records or any(r.metadata["backend"] != "mock" for r in records):
        raise ValueError("automatic segment boundaries are available only for mock traces")
    if len({(r.truth["variant"],r.truth["x"],r.truth["y"]) for r in records}) != 1:
        raise ValueError("evaluate one variant and index pair at a time")
    grouped = {}
    for record in records:
        settings = record.metadata["settings"]
        width = settings["samples_per_candidate"]
        if not 0 <= candidate_index < len(record.truth["candidates"]):
            continue
        start = settings["prefix"]+candidate_index*width
        segment = record.wave[start:start+width]
        grouped.setdefault(record.truth["seed"],[]).append(
            (segment,int(record.truth["valid"][candidate_index])))
    seeds = sorted(grouped)
    X = np.array([np.mean([p[0] for p in grouped[s]],axis=0) for s in seeds])
    y = np.array([grouped[s][0][1] for s in seeds])
    if len(np.unique(y)) != 2 or np.min(np.bincount(y)) < 4:
        raise ValueError("need at least four distinct seeds in each class")
    return X,y,seeds


def evaluate_mock(records, candidate_index=0, split_seed=123):
    X,y,seeds = mock_seed_segments(records,candidate_index)
    train,test = train_test_split(np.arange(len(y)),test_size=0.3,
                                 stratify=y,random_state=split_seed)
    model = make_pipeline(StandardScaler(),LogisticRegression(
        class_weight="balanced",max_iter=1000,random_state=split_seed))
    model.fit(X[train],y[train])
    pred, score = model.predict(X[test]),model.predict_proba(X[test])[:,1]
    dummy = DummyClassifier(strategy="most_frequent").fit(X[train],y[train])
    # Descriptive Welch test on one predeclared scalar per training seed.
    # It is not a full TVLA evaluation and is not used to select features.
    scalar = X[train].mean(axis=1)
    stat = ttest_ind(scalar[y[train]==1],scalar[y[train]==0],equal_var=False)
    return {"synthetic":True,"candidate_index":candidate_index,
        "independent_train_seeds":len(train),"independent_test_seeds":len(test),
        "train_seeds":[seeds[i] for i in train],"test_seeds":[seeds[i] for i in test],
        "positive_class":"candidate < 3329 (valid)",
        "balanced_accuracy":float(balanced_accuracy_score(y[test],pred)),
        "precision_valid":float(precision_score(y[test],pred,zero_division=0)),
        "recall_valid":float(recall_score(y[test],pred,zero_division=0)),
        "roc_auc":float(roc_auc_score(y[test],score)),
        "confusion_matrix_reject_valid":confusion_matrix(y[test],pred,labels=[0,1]).tolist(),
        "majority_balanced_accuracy":float(balanced_accuracy_score(y[test],dummy.predict(X[test]))),
        "descriptive_train_welch_t":float(stat.statistic),
        "descriptive_train_welch_p":float(stat.pvalue),
        "interpretation":"Mock pipeline check only; no measured hardware leakage established."}
