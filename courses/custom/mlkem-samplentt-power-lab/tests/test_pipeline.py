import json
import numpy as np
import pytest
from analysis.ground_truth import generated_seed, output_digest
from analysis.evaluate import evaluate_mock, mock_seed_segments
from simulation.mock import MockBackend, MockSettings
from capture.records import acquire_batch, save_dataset, load_dataset


def test_mock_repeatability_and_fixed_schedule():
    seed = generated_seed(0)
    a,b = MockBackend(),MockBackend()
    for variant in ["variable_time","fls"]:
        left,right = a.capture(seed,variant=variant),b.capture(seed,variant=variant)
        np.testing.assert_array_equal(left.wave,right.wave)
        assert left.metadata["synthetic"]
        assert left.metadata["verification_digest"] == output_digest(left.truth["coefficients"]).hex()
    no_jitter=MockBackend(MockSettings(timing_noise_sd=0))
    times=[no_jitter.capture(generated_seed(i),variant="fls").metadata["timing_value"] for i in range(5)]
    assert len(set(times)) == 1


def test_save_load_and_seed_grouping(tmp_path):
    records,errors = acquire_batch(MockBackend(),[generated_seed(i) for i in range(96)],"fls",repeats=2)
    assert not errors and len(records) == 192
    directory=save_dataset(tmp_path/"dataset",records,errors,{"mock":True})
    restored,manifest=load_dataset(directory)
    assert manifest["count"] == 192
    np.testing.assert_array_equal(records[0].wave,restored[0].wave)
    result=evaluate_mock(restored)
    assert not set(result["train_seeds"]) & set(result["test_seeds"])
    assert result["independent_train_seeds"]+result["independent_test_seeds"] == 96
    assert result["majority_balanced_accuracy"] == 0.5
    assert 0 <= result["roc_auc"] <= 1
    json.dumps(result,allow_nan=False)
    with pytest.raises(FileExistsError):
        save_dataset(directory,records,errors,{})


def test_failure_records_keep_input_identity():
    class FailingBackend:
        def capture(self,*args):
            raise TimeoutError("injected test failure")
    seed=generated_seed(1)
    records,errors=acquire_batch(FailingBackend(),[seed],"variable_time",repeats=2)
    assert not records and len(errors) == 2
    assert errors[0]["seed"] == seed.hex()


def test_mock_boundaries_refuse_hardware():
    record=MockBackend().capture(generated_seed(0))
    record.metadata["backend"]="chipwhisperer"
    with pytest.raises(ValueError,match="only for mock"):
        mock_seed_segments([record])
