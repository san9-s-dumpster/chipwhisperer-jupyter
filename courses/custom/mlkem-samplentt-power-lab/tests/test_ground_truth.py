import hashlib
import json
from pathlib import Path
import pytest
from analysis.ground_truth import (ground_truth, from_stream, decode_candidates,
    encode_input, generated_seed, output_digest, VARIANTS)
from analysis.c_reference import CReference, build_reference, verify_sources


@pytest.fixture(scope="session")
def c_reference(tmp_path_factory):
    return CReference(build_reference(tmp_path_factory.mktemp("c-reference")))


def pack(values):
    result = bytearray()
    for a,b in zip(values[::2], values[1::2]):
        result.extend((a & 255, (a >> 8) | ((b & 15) << 4), b >> 4))
    return bytes(result)


def test_source_integrity():
    assert len(verify_sources()["commit"]) == 40


def test_candidate_boundaries_and_byte_order():
    values = [0, 3328, 3329, 4095, 1, 256]
    assert decode_candidates(pack(values)) == values
    assert encode_input(bytes(range(32)), 2, 1)[-2:] == b"\x02\x01"
    assert ground_truth(bytes(32),1,2).coefficients != ground_truth(bytes(32),2,1).coefficients


@pytest.mark.parametrize("seed,x,y", [(b"short",0,0),(bytes(32),-1,0),
    (bytes(32),0,256),(bytes(32),True,0)])
def test_invalid_inputs(seed,x,y):
    with pytest.raises(ValueError):
        ground_truth(seed,x,y)


def test_regression_vectors(c_reference):
    data = json.loads((Path(__file__).parent/"vectors.json").read_text())
    for vec in data["vectors"]:
        for variant in VARIANTS:
            gt = ground_truth(bytes.fromhex(vec["seed"]),vec["x"],vec["y"],variant)
            assert gt.coefficients == vec["coefficients"]
            assert c_reference.sample(bytes.fromhex(vec["seed"]),vec["x"],vec["y"],variant) == vec["coefficients"]
            assert output_digest(gt.coefficients).hex() == vec["sha3_256_le16"]


@pytest.mark.parametrize("number", range(48))
def test_deterministic_seeds_against_independent_c(number,c_reference):
    seed = generated_seed(number,"correctness-v1")
    x,y = number % 4,(number // 4) % 4
    for variant in VARIANTS:
        gt = ground_truth(seed,x,y,variant)
        assert gt.complete
        assert gt.coefficients == c_reference.sample(seed,x,y,variant)
        assert sum(gt.committed) == 256
        assert all(0 <= c < 3329 for c in gt.coefficients)
        if variant == "fls":
            assert len(gt.candidates) == 560
            assert gt.pair_iterations == 280
            assert gt.xof_bytes_requested == 840
            assert gt.xof_rate_blocks == 5
            assert not any(gt.committed[gt.candidates_to_fill:])


def test_final_pair_and_after_full_flags():
    stream = pack([1]*560)
    vt = from_stream(bytes(32),0,0,"variable_time",stream)
    fls = from_stream(bytes(32),0,0,"fls",stream)
    assert len(vt.candidates) == 256
    assert all(fls.valid) and sum(fls.committed) == 256
    assert fls.counter_before[256] == 256
    assert not any(fls.tentative_update[256:])
    # Fill on the first candidate of a pair: second is decoded and valid,
    # but it must not become a 257th output word.
    vt = from_stream(bytes(32),0,0,"variable_time",pack([4095]+[1]*559))
    assert vt.candidates_to_fill == 257
    assert len(vt.candidates) == 258
    assert vt.valid[-1] and not vt.committed[-1]


def test_rejection_is_not_commit_or_speculative_update():
    fls = from_stream(bytes(32),0,0,"fls",pack([4095,7]+[1]*558))
    assert not fls.valid[0] and not fls.committed[0]
    assert fls.tentative_update[0] and fls.tentative_update[1]
    assert fls.coefficients[0] == 7


def test_fixed_schedule_shortfall_is_explicit():
    for variant in VARIANTS:
        gt = from_stream(bytes(32),0,0,variant,pack([4095]*560))
        assert not gt.complete and gt.candidates_to_fill is None
        assert len(gt.candidates) == 560 and sum(gt.committed) == 0


def test_shake_known_prefix():
    # FIPS 202 SHAKE128 empty-message prefix, independent of SampleNTT.
    assert hashlib.shake_128(b"").hexdigest(16) == "7f9c2ba4e88f827d616045507605853e"
