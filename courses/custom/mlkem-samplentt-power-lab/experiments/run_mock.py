"""Run the same mock experiment outside Jupyter, saving data and figures."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from analysis.ground_truth import generated_seed
from analysis.evaluate import evaluate_mock
from analysis.plots import plot_mock_summary
from capture.records import acquire_batch,save_dataset
from simulation.mock import MockBackend,MockSettings


def run(seed_count=96,repeats=2,noise_sd=0.85):
    if seed_count < 32:
        raise ValueError("use at least 32 seeds for the mock classification demonstration")
    run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid4().hex[:8]
    directory=ROOT/"results/runs"/run_id
    directory.mkdir(parents=True)
    settings=MockSettings(noise_sd=noise_sd)
    backend=MockBackend(settings)
    datasets,metrics={},{}
    seeds=[generated_seed(i) for i in range(seed_count)]
    for variant in ["variable_time","fls"]:
        records,failures=acquire_batch(backend,seeds,variant,repeats=repeats)
        save_dataset(directory/variant,records,failures,asdict(settings))
        datasets[variant]=records
        metrics[variant]=evaluate_mock(records)
    (directory/"metrics.json").write_text(json.dumps(metrics,indent=2)+"\n")
    plot_mock_summary(datasets).savefig(directory/"synthetic-summary.png",dpi=160)
    return directory


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds",type=int,default=96)
    parser.add_argument("--repeats",type=int,default=2)
    parser.add_argument("--noise-sd",type=float,default=0.85)
    args=parser.parse_args()
    print(run(args.seeds,args.repeats,args.noise_sd))
