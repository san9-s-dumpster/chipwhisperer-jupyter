"""Hardware workflow for the short SampleNTT proof notebook. No mock fallback."""
from contextlib import suppress
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import time
from uuid import uuid4
import numpy as np
from tqdm.auto import tqdm
from analysis.ground_truth import generated_seed
from analysis.distinguisher import make_plan,load_plan
from analysis.proof import freeze_classifier,load_classifier,evaluate
from capture.hardware import HardwareBackend,HardwareSettings
from capture.records import save_dataset
from capture.cohort import acquire_cohort,read_cohort
from firmware.build import build


def normal_husky_bus(serial=None):
    from chipwhisperer.hardware.naeusb.naeusb import NAEUSB
    link=NAEUSB()
    try:
        link.con(idProduct=[0xACE5],serial_number=serial)
        link.cmdWriteMem(36,bytearray([0]))
        link.set_smc_speed(0)
    finally:link.close()


class SampleNTTPowerLab:
    def __init__(self,repo,per_class=128,gain_db=10.,serial=None,resume=None):
        self.repo=Path(repo).expanduser().resolve()
        self.root=self.repo/'jupyter/courses/custom/mlkem-samplentt-power-lab'
        self.preset=json.loads((self.root/'proof-preset.json').read_text())
        self.per_class,self.gain_db,self.serial=per_class,gain_db,serial
        if per_class<16:raise ValueError('use at least 16 independent seeds per class')
        self.run_path=Path(resume).expanduser().resolve() if resume else self.root/'results/runs'/('proof-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:6])
        if resume and not self.run_path.is_dir():raise FileNotFoundError(self.run_path)
        self.run_path.mkdir(parents=True,exist_ok=True)
        self.scope=self.target=self.recorder=None
        self.plan=load_plan(self.run_path/'plan.json') if (self.run_path/'plan.json').exists() else None
        self.frozen_path=self.run_path/'frozen-model.json'
        self.cw=importlib.import_module('chipwhisperer')
        print('Results:',self.run_path)

    def _reset_target(self):
        self.scope.io.nrst='low';time.sleep(.05)
        self.scope.io.nrst='high_z';time.sleep(.25)
        self.target.flush()

    def prepare(self):
        if self.scope is not None:
            raise RuntimeError('Already connected. Continue, or disconnect before preparing a new session.')
        try:
            record=build(self.repo,self.preset['target_platform'],'variable_time',profile='measurement')
            if record['firmware_sha256']!=self.preset['firmware_sha256']:
                raise ValueError('This image differs from the calibrated image. Use the full-method notebook to recalibrate; no target was programmed.')
            normal_husky_bus(self.serial)
            self.scope=self.cw.scope(sn=self.serial)
            scope=self.scope
            if 'husky' not in str(scope).lower():raise ValueError('this lab requires Husky')
            scope.default_setup(verbose=False)
            scope.clock.clkgen_freq=self.preset['target_clock_hz']
            scope.clock.adc_mul=self.preset['adc_multiplier']
            scope.io.hs2='clkgen'
            scope.io.tio1,scope.io.tio2,scope.io.tio3='serial_rx','serial_tx','high_z'
            scope.trigger.module='basic';scope.trigger.triggers='tio4'
            scope.adc.stream_mode=False;scope.adc.presamples=0
            scope.adc.segments=1;scope.adc.decimate=1
            scope.adc.samples=self.preset['samples'];scope.adc.offset=self.preset['offset']
            scope.adc.basic_mode='rising_edge';scope.adc.timeout=10
            scope.gain.db=self.gain_db;scope.adc.errors=0
            time.sleep(.25)
            if not scope.clock.adc_locked:raise RuntimeError('ADC clock did not lock')
            self.target=self.cw.target(scope,self.cw.targets.SimpleSerial)
            self.target.baud=self.preset['baud']
            self.cw.program_target(scope,self.cw.programmers.STM32FProgrammer,record['image'])
            self._reset_target()
            settings=HardwareSettings('Husky',self.preset['target_platform'],
                str(self.root/'firmware/variable_time/build.json'),str(scope.sn),
                target_clock_hz=float(scope.clock.clkgen_freq),adc_multiplier=int(scope.clock.adc_mul),
                samples=int(scope.adc.samples),offset=int(scope.adc.offset),gain_db=float(scope.gain.db),
                baud=int(self.target.baud),timeout_seconds=float(scope.adc.timeout),stream_mode=False)
            self.recorder=HardwareBackend.from_connected(scope,self.target,settings,self.cw.__version__)
            # First call warms allocator/state. Only the second is displayed;
            # neither contributes to training or test performance.
            checks=[self.recorder.capture(generated_seed(i,'proof-warmup-v1')) for i in (0,1)]
            save_dataset(self.run_path/('capture-check-'+uuid4().hex[:6]),checks,[],{'purpose':'warmup and verified check'})
            print('Verified measurement firmware:',record['firmware_sha256'])
            print('Digest checks passed; ADC range:',int(checks[1].wave.min()),'to',int(checks[1].wave.max()))
            return checks[1]
        except BaseException:
            with suppress(Exception):self.close()
            raise

    def _ensure_ready(self):
        if self.recorder is None:raise RuntimeError('Run the hardware preparation cell first.')

    def _ensure_plan(self):
        if self.plan is not None:return
        excluded={generated_seed(i,'proof-warmup-v1').hex() for i in (0,1)}
        for path in (self.root/'results/runs').rglob('plan.json'):
            if self.run_path in path.parents:continue
            prior=json.loads(path.read_text())
            for seeds in prior.get('cohorts',{}).values():excluded.update(seeds)
        # Historical v1 data predate plan.json.
        for path in (self.root/'results/runs').glob('*/**/manifest.json'):
            if self.run_path in path.parents:continue
            manifest=json.loads(path.read_text())
            if manifest.get('settings',{}).get('role') in ('development','holdout'):continue
            for stem in manifest.get('records',[]):
                item=path.parent/(stem+'.json')
                if item.is_file():excluded.add(json.loads(item.read_text())['truth']['seed'])
        self.plan=make_plan(self.run_path/'plan.json',per_class=self.per_class,repeats=1,
                            pair_iterations=self.preset['pair_iterations'],excluded=excluded)

    def collect_training(self):
        self._ensure_ready();self._ensure_plan()
        records=acquire_cohort(self.recorder,self.plan,'development',self.run_path/'development',
            progress=lambda items:tqdm(items,desc='Training captures'))
        print(len(records),'verified training captures; one per seed.')
        return len(records)

    def freeze(self):
        self._ensure_plan()
        records=read_cohort(self.run_path/'development')
        if not records:raise RuntimeError('Capture the training cohort before freezing the classifier.')
        frozen=freeze_classifier(self.frozen_path,records,self.plan,self.preset)
        print('Classifier frozen:',frozen['sha256'])
        print('Window fixed before collection; sample points fitted using training data only.')
        return frozen['sha256']

    def collect_test(self):
        self._ensure_ready();self._ensure_plan()
        if not self.frozen_path.is_file():raise RuntimeError('Freeze the classifier before fresh-test capture.')
        load_classifier(self.frozen_path)
        records=acquire_cohort(self.recorder,self.plan,'holdout',self.run_path/'holdout',
            frozen_path=self.frozen_path,progress=lambda items:tqdm(items,desc='Fresh test captures'))
        print(len(records),'verified fresh-test captures; model unchanged.')
        return len(records)

    def results(self):
        from IPython.display import display,Markdown
        from analysis.proof_plots import result_figure
        self._ensure_plan()
        frozen=load_classifier(self.frozen_path)
        report,X,y,scores=evaluate(read_cohort(self.run_path/'holdout'),self.plan,frozen)
        report['acquisition_audit']={}
        for role in ('development','holdout'):
            attempts=[json.loads(s) for s in (self.run_path/role/'attempts.jsonl').read_text().splitlines()]
            report['acquisition_audit'][role]=[a for a in attempts if a['status']!='ok']
        (self.run_path/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        rows=['| Model | Correct | Balanced accuracy (95% CI) | AUC |','|---|---:|---:|---:|']
        for key,title in [('power','Power'),('timing','Total timing')]:
            m=report['metrics'][key];lo,hi=m['balanced_accuracy_95ci']
            rows.append(f"| {title} | {m['correct']}/{report['n_test_seeds']} | {100*m['balanced_accuracy']:.1f}% ({100*lo:.1f}–{100*hi:.1f}%) | {m['roc_auc']:.3f} |")
        display(Markdown('\n'.join(rows)))
        p=report['metrics']['power']['exact_test_label_permutation_p']
        print('Chance balanced accuracy: 50%. Fixed-model label-permutation p:',f'{p:.3g}')
        print('Evidence supports first-candidate discrimination in this setup.' if report['supported'] else 'This run does not establish a convincing distinguisher.')
        if any(report['acquisition_audit'].values()):print('Inspect report.json for failed/retried captures before interpreting the result.')
        fig=result_figure(X,y,scores,self.preset,float(frozen['signature']['adc_frequency_hz']))
        fig.savefig(self.run_path/'result.png',dpi=160)
        display(fig)
        import matplotlib.pyplot as plt
        plt.close(fig)
        print('Saved:',self.run_path/'report.json')
        return report

    def close(self):
        if self.target is not None:
            with suppress(Exception):self.target.dis()
            self.target=None
        if self.scope is not None:
            try:
                if hasattr(self.scope,'sc'):
                    with suppress(Exception):self.scope.sc.setFastSMC(0)
            finally:
                self.scope.dis();self.scope=None;self.recorder=None
