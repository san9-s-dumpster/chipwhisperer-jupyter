"""Checkpointed, randomized physical acquisition for a predeclared seed cohort."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
import numpy as np
from analysis.distinguisher import load_frozen, signature
from capture.records import load_dataset, save_dataset


def read_cohort(directory):
    directory = Path(directory)
    records = []
    for chunk in sorted(directory.glob('trial-*/manifest.json')):
        group, manifest = load_dataset(chunk.parent)
        if len(group) != 1 or manifest['failures']:
            raise ValueError(f'invalid checkpoint: {chunk.parent}')
        records.extend(group)
    return records


def acquire_cohort(backend, plan, role, directory, frozen_path=None, progress=None):
    """Save every success immediately. Rerun to resume after a failure/interruption.

    Trial order is fixed before capture. Failures stop acquisition and are kept
    in attempts.jsonl; no incomplete cohort can pass final analysis.
    """
    if role not in ('development','holdout'):
        raise ValueError('unknown cohort')
    if backend.build.get('profile','measurement') != 'measurement' or backend.build['variant'] != 'variable_time':
        raise ValueError('restore representative variable-time firmware before collecting cohorts')
    frozen = None
    if role == 'holdout':
        if frozen_path is None:
            raise ValueError('freeze the model before acquiring any holdout traces')
        frozen = load_frozen(frozen_path)
        if frozen['plan_sha256'] != plan['sha256']:
            raise ValueError('frozen model belongs to another plan')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    header = dict(plan_sha256=plan['sha256'], role=role,
                  frozen_sha256=None if frozen is None else frozen['sha256'])
    header_path = directory/'cohort.json'
    if header_path.exists():
        if json.loads(header_path.read_text()) != header:
            raise ValueError('checkpoint belongs to another plan/model')
    else:
        with header_path.open('x') as f:
            json.dump(header,f,indent=2)
    trials = [(seed, rep) for seed in plan['cohorts'][role] for rep in range(plan['repeats'])]
    existing = read_cohort(directory)
    reference = frozen['signature'] if frozen else (signature(existing[0]) if existing else None)
    order = np.random.default_rng(plan['order_seed'] + int(role=='holdout')).permutation(len(trials))
    pending = [(position,int(trial)) for position,trial in enumerate(order)
               if not (directory/f'trial-{int(trial):05d}'/'manifest.json').exists()]
    if progress:
        pending = progress(pending)
    for position, trial in pending:
        seed, rep = trials[trial]
        entry = dict(utc=datetime.now(timezone.utc).isoformat(), trial=trial, seed=seed, repeat=rep)
        try:
            record = backend.capture(bytes.fromhex(seed),plan['x'],plan['y'],'variable_time')
            record.metadata.update(plan_sha256=plan['sha256'], cohort=role, repeat=rep,
                trial=trial, sequence=position, acquisition_utc=entry['utc'],
                frozen_sha256=header['frozen_sha256'])
            if reference is None:
                reference = signature(record)
            if signature(record) != reference:
                raise ValueError('capture conditions changed from the existing cohort/frozen model')
            # Commit a complete checkpoint with one atomic directory rename.
            # An interrupt during compression must not poison a resumed trial.
            temporary = Path(tempfile.mkdtemp(prefix='.pending-',dir=directory))
            try:
                save_dataset(temporary/'record',[record],[],header)
                os.replace(temporary/'record',directory/f'trial-{trial:05d}')
            finally:
                shutil.rmtree(temporary,ignore_errors=True)
            entry['status'] = 'ok'
        except BaseException as error:
            entry.update(status='failed', error=f'{type(error).__name__}: {error}')
            with (directory/'attempts.jsonl').open('a') as f:
                f.write(json.dumps(entry)+'\n')
            raise
        with (directory/'attempts.jsonl').open('a') as f:
            f.write(json.dumps(entry)+'\n')
    return read_cohort(directory)
