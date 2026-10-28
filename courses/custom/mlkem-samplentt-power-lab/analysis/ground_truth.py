"""Independent SHAKE128/SampleNTT labels, using Python's hashlib backend."""
from dataclasses import asdict, dataclass
import hashlib

Q, N, MAX_ITER, RATE = 3329, 256, 280, 168
VARIANTS = ("variable_time", "fls")


@dataclass
class GroundTruth:
    seed: str
    x: int
    y: int
    variant: str
    coefficients: list[int]
    candidates: list[int]
    valid: list[bool]
    committed: list[bool]
    counter_before: list[int]
    tentative_update: list[bool]
    pair_iterations: int
    candidates_to_fill: int | None
    xof_bytes_requested: int
    xof_rate_blocks: int
    complete: bool

    def to_dict(self):
        return asdict(self)


def encode_input(seed: bytes, x: int, y: int) -> bytes:
    """Literal byte order rho || x || y. For A[row,col], x=col,y=row."""
    if not isinstance(seed, bytes) or len(seed) != 32:
        raise ValueError("seed must be exactly 32 bytes")
    if any(type(i) is not int or not 0 <= i <= 255 for i in (x, y)):
        raise ValueError("x and y must be byte-valued integers")
    return seed + bytes((x, y))


def decode_candidates(stream: bytes) -> list[int]:
    if len(stream) % 3:
        raise ValueError("candidate stream must contain whole three-byte pairs")
    values = []
    for p in range(0, len(stream), 3):
        b0, b1, b2 = stream[p:p+3]
        values.extend((b0 | ((b1 & 15) << 8), (b1 >> 4) | (b2 << 4)))
    return values


def from_stream(seed: bytes, x: int, y: int, variant: str, stream: bytes) -> GroundTruth:
    """Model the pinned top-level A0/A1, including A1's speculative writes.

    This exposes an incomplete fixed schedule rather than inventing a fallback.
    It is not a Python implementation intended to run in constant time.
    """
    encode_input(seed, x, y)
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    if len(stream) != 3 * MAX_ITER:
        raise ValueError("expected the complete 280-pair XOF prefix")
    values = decode_candidates(stream)
    output = [0] * N
    seen, valid, committed, before, tentative = [], [], [], [], []
    ctr, fill = 0, None
    for pair in range(MAX_ITER):
        for value in values[2*pair:2*pair+2]:
            ok, in_range = value < Q, ctr < N
            seen.append(value)
            valid.append(ok)
            before.append(ctr)
            committed.append(ok and in_range)
            # Top-level A1 writes at ctr even for a rejected candidate; the
            # next candidate overwrites it. pqm4 A1 has different masking.
            tentative.append(variant == "fls" and in_range)
            if in_range and (ok or variant == "fls"):
                output[ctr] = value
            if ok and (variant == "fls" or in_range):
                ctr += 1
            if ctr >= N and fill is None:
                fill = len(seen)
        if variant == "variable_time" and ctr >= N:
            break
    iterations = len(seen) // 2
    return GroundTruth(seed.hex(), x, y, variant, output, seen, valid,
                       committed, before, tentative, iterations, fill,
                       3*iterations, (3*iterations+RATE-1)//RATE, fill is not None)


def ground_truth(seed: bytes, x: int = 0, y: int = 0,
                 variant: str = "variable_time") -> GroundTruth:
    extseed = encode_input(seed, x, y)
    # digest(n) returns a prefix, not the next n bytes. Request it once.
    return from_stream(seed, x, y, variant,
                       hashlib.shake_128(extseed).digest(3*MAX_ITER))


def output_digest(coefficients: list[int]) -> bytes:
    if len(coefficients) != N or any(not 0 <= c <= 65535 for c in coefficients):
        raise ValueError("expected 256 unsigned 16-bit words")
    encoded = b"".join(c.to_bytes(2, "little") for c in coefficients)
    return hashlib.sha3_256(encoded).digest()


def generated_seed(number: int, domain: str = "demo-v1") -> bytes:
    if number < 0:
        raise ValueError("seed number must be non-negative")
    return hashlib.sha256(f"samplentt-lab:{domain}:{number}".encode()).digest()
