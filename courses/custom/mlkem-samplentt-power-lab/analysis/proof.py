"""Fixed-window, single-trace proof with exact uncertainty and a frozen test.

No test data choose the window, features, fit, threshold or score direction.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.stats import beta, hypergeom
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, roc_auc_score
from analysis import distinguisher as core


def _source_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def freeze_classifier(path, records, plan, preset):
    path=Path(path)
    if path.exists():
        return load_classifier(path)
    X,y,t,seeds,signature=core.cohort_arrays(records,plan,'development')
    if plan['repeats']!=1:
        raise ValueError('the short lab uses exactly one trace per seed')
    if signature['firmware_sha256']!=preset['firmware_sha256']:
        raise ValueError('firmware differs from the calibrated image')
    record=dict(schema=3,kind='fixed-window-single-trace-proof',plan_sha256=plan['sha256'],
        signature=signature,development_seeds=seeds,roi=[0,X.shape[1]],
        models={'single_trace':{'power':core._linear_fit(X,y),
                                'timing':core._linear_fit(t,y,False)}},
        decision_threshold=.5,primary='single_trace',
        source_sha256=hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),
        proof_source_sha256=_source_hash(),preset=preset,
        development_fingerprint=core.records_fingerprint(records),
        frozen_utc=datetime.now(timezone.utc).isoformat())
    record['sha256']=core.digest(record)
    with path.open('x') as stream:json.dump(record,stream,indent=2)
    return record


def load_classifier(path):
    record=core.load_frozen(path)
    if record.get('kind')!='fixed-window-single-trace-proof' or record.get('proof_source_sha256')!=_source_hash():
        raise ValueError('proof code/model changed; start a fresh experiment')
    return record


def exact_recall_bounds(y,predicted):
    """Simultaneous >=95% bounds: two 97.5% Clopper-Pearson class intervals."""
    intervals=[]
    for label in (0,1):
        n=int(np.sum(y==label));k=int(np.sum(predicted[y==label]==label))
        if not n:raise ValueError('need both classes')
        intervals.append([0. if not k else float(beta.ppf(.0125,k,n-k+1)),
                          1. if k==n else float(beta.ppf(.9875,k+1,n-k))])
    return intervals,np.mean(intervals,axis=0).tolist()


def exact_label_permutation_p(y,predicted):
    n1=int(np.sum(y==1));m=int(np.sum(predicted));tp=int(np.sum((y==1)&predicted))
    return float(hypergeom.sf(tp-1,len(y),n1,m))


def evaluate(records, plan, frozen):
    if frozen['plan_sha256']!=plan['sha256']:
        raise ValueError('model belongs to a different experiment')
    if set(frozen['development_seeds'])&set(plan['cohorts']['holdout']):
        raise ValueError('training/test seeds overlap')
    if any(r.metadata.get('frozen_sha256')!=frozen['sha256'] for r in records):
        raise ValueError('test captures must follow this frozen fit')
    X,y,t,seeds,signature=core.cohort_arrays(records,plan,'holdout')
    if signature!=frozen['signature']:
        raise ValueError('test capture conditions changed')
    result=dict(schema=1,n_test_seeds=len(seeds),plan_sha256=plan['sha256'],
        frozen_sha256=frozen['sha256'],test_fingerprint=core.records_fingerprint(records),
        metrics={},scope='First candidate, balanced workload-conditioned public seeds, warm target, one device/build.')
    scores={}
    for name,features in [('power',X),('timing',t)]:
        score=core._score(frozen['models']['single_trace'][name],features)
        predicted=score>=0;scores[name]=score
        per_class,bounds=exact_recall_bounds(y,predicted)
        cm=confusion_matrix(y,predicted,labels=[0,1])
        # Under independently permuted test labels, true positives follow a
        # hypergeometric law. BA increases monotonically with true positives.
        p=exact_label_permutation_p(y,predicted)
        result['metrics'][name]=dict(balanced_accuracy=float(balanced_accuracy_score(y,predicted)),
            balanced_accuracy_95ci=bounds,recall_intervals_simultaneous_95=per_class,
            roc_auc=float(roc_auc_score(y,score)),confusion_matrix_reject_accept=cm.tolist(),
            correct=int(np.sum(predicted==y)),exact_test_label_permutation_p=p)
    primary=result['metrics']['power']
    result['supported']=primary['balanced_accuracy_95ci'][0]>.5 and primary['exact_test_label_permutation_p']<.05
    return result,X,y,scores
