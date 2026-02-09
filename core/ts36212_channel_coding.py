"""LTE channel coding helpers (3GPP TS 36.212).

This simulator is not a full LTE PHY stack (no PDSCH/PUSCH scheduling, no HARQ,
no rate matching to a specific E). The goal here is to provide a **real LTE
standard-compatible** forward-error-correction building block that can be
enabled/disabled from the UI.

Implemented (TS 36.212):
  - CRC attachment/check: CRC24A, CRC24B, CRC16, CRC8.
  - Convolutional coding: rate 1/3, constraint length 7, polynomials
    G0=133, G1=171, G2=165 (octal).

Decoder:
  - Hard-decision Viterbi decoder for the above code.
  - To keep the simulator fast for large payloads (images), the default mode
    uses **termination** (adds 6 tail zeros). TS 36.212 control channels use
    **tail-biting**; you can enable tail-biting encoding as well, but decoding
    tail-biting optimally requires wrap-around Viterbi (WAVA) which is more
    expensive. For now, tail-biting is supported in the encoder, and the
    decoder supports termination (recommended for this project).

References for polynomials and convolutional code:
  - TS 36.212 CRC polynomials and convolutional polynomials (ETSI/3GPP).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

import numpy as np


CRCName = Literal["24A", "24B", "16", "8"]


def _poly_to_int(degrees: Tuple[int, ...]) -> int:
    """Return polynomial (excluding top term) as int bitmask.

    Example: CRC16 polynomial D^16 + D^12 + D^5 + 1
    => degrees (12,5,0) with top degree 16 excluded from mask.
    """
    out = 0
    for d in degrees:
        out |= 1 << d
    return out


# TS 36.212 CRC generator polynomials (degrees of non-zero terms EXCLUDING D^L)
# gCRC24A(D) = D^24 + D^23 + D^18 + D^17 + D^14 + D^11 + D^10 + D^7 + D^6 + D^5 + D^4 + D^3 + D + 1
# gCRC24B(D) = D^24 + D^23 + D^6 + D^5 + D + 1
# gCRC16(D)  = D^16 + D^12 + D^5 + 1
# gCRC8(D)   = D^8 + D^7 + D^4 + D^3 + D + 1
_CRC_POLYS = {
    "24A": (24, _poly_to_int((23, 18, 17, 14, 11, 10, 7, 6, 5, 4, 3, 1, 0))),
    "24B": (24, _poly_to_int((23, 6, 5, 1, 0))),
    "16": (16, _poly_to_int((12, 5, 0))),
    "8": (8, _poly_to_int((7, 4, 3, 1, 0))),
}


def crc_attach(bits: np.ndarray, crc: CRCName = "24A") -> np.ndarray:
    """Append CRC parity bits (systematic CRC) to `bits`."""
    bits = np.asarray(bits, dtype=np.uint8)
    L, poly = _CRC_POLYS[crc]
    mask = (1 << L) - 1
    reg = 0

    # process message bits
    for b in bits.tolist():
        msb = (reg >> (L - 1)) & 1
        fb = msb ^ int(b)
        reg = ((reg << 1) & mask)
        if fb:
            reg ^= poly

    # process L zero bits (append zeros)
    for _ in range(L):
        msb = (reg >> (L - 1)) & 1
        fb = msb
        reg = ((reg << 1) & mask)
        if fb:
            reg ^= poly

    parity = np.array([(reg >> (L - 1 - i)) & 1 for i in range(L)], dtype=np.uint8)
    return np.concatenate([bits, parity])


def crc_check(bits_with_crc: np.ndarray, crc: CRCName = "24A") -> Tuple[np.ndarray, bool]:
    """Check CRC and return (payload_bits, ok)."""
    bits_with_crc = np.asarray(bits_with_crc, dtype=np.uint8)
    L, poly = _CRC_POLYS[crc]
    if bits_with_crc.size < L:
        return bits_with_crc, False

    mask = (1 << L) - 1
    reg = 0
    for b in bits_with_crc.tolist():
        msb = (reg >> (L - 1)) & 1
        fb = msb ^ int(b)
        reg = ((reg << 1) & mask)
        if fb:
            reg ^= poly
    ok = (reg == 0)
    return bits_with_crc[:-L].copy(), ok


def _octal_to_int(oct_val: int) -> int:
    return int(str(oct_val), 8)


@dataclass(frozen=True)
class ConvCodeConfig:
    """LTE convolutional code (TS 36.212) configuration."""

    constraint_len: int = 7
    # generator polynomials in octal (TS 36.212): 133, 171, 165
    generators_octal: Tuple[int, int, int] = (133, 171, 165)

    @property
    def generators(self) -> Tuple[int, int, int]:
        gens = tuple(_octal_to_int(g) for g in self.generators_octal)
        # ensure 7-bit mask
        return tuple(g & ((1 << self.constraint_len) - 1) for g in gens)

    @property
    def memory(self) -> int:
        return self.constraint_len - 1

    @property
    def n_states(self) -> int:
        return 1 << self.memory


_DEFAULT_CONV = ConvCodeConfig()


def conv_encode(
    bits: np.ndarray,
    *,
    terminate: bool = True,
    tail_biting: bool = False,
    cfg: ConvCodeConfig = _DEFAULT_CONV,
) -> np.ndarray:
    """Rate-1/3 convolutional encoder (TS 36.212 polynomials).

    Parameters
    ----------
    bits:
        Input bits (0/1).
    terminate:
        If True, appends `memory` zeros (6) to force trellis termination.
        Recommended for this simulator.
    tail_biting:
        If True, uses tail-biting initialization (initial state set from last
        `memory` bits). In TS 36.212, control channels use tail-biting.
        NOTE: Optimal tail-biting decoding is more complex; decoder in this
        module supports termination (default).
    """
    bits = np.asarray(bits, dtype=np.uint8)
    m = cfg.memory
    gens = cfg.generators

    if tail_biting and bits.size >= m:
        # initial state from last m bits (s0..s5), MSB is last bit
        last = bits[-m:]
        state = 0
        for i, b in enumerate(last):
            state |= int(b) << (m - 1 - i)
    else:
        state = 0

    if terminate and not tail_biting:
        in_bits = np.concatenate([bits, np.zeros(m, dtype=np.uint8)])
    else:
        in_bits = bits

    out = np.empty(in_bits.size * 3, dtype=np.uint8)

    idx = 0
    for b in in_bits.tolist():
        u = int(b)
        reg = (u << m) | state  # 7-bit register: [u, s0..s5]

        for g in gens:
            # parity of AND
            v = reg & g
            # python >=3.8: int.bit_count
            out[idx] = (v.bit_count() & 1)
            idx += 1

        # update state: new_state = [u, s0..s4]
        state = ((u << (m - 1)) | (state >> 1)) & ((1 << m) - 1)

    return out


def _build_trellis(cfg: ConvCodeConfig = _DEFAULT_CONV):
    """Precompute trellis arrays for fast Viterbi decoding."""
    m = cfg.memory
    n_states = cfg.n_states
    gens = cfg.generators

    # next_state[p, u] and out_bits[p, u, j]
    next_state = np.zeros((n_states, 2), dtype=np.uint8)
    out_bits = np.zeros((n_states, 2, 3), dtype=np.uint8)

    for p in range(n_states):
        for u in (0, 1):
            reg = (u << m) | p
            bits = []
            for g in gens:
                v = reg & g
                bits.append(v.bit_count() & 1)
            out_bits[p, u, :] = bits
            ns = ((u << (m - 1)) | (p >> 1)) & (n_states - 1)
            next_state[p, u] = ns

    return next_state, out_bits


_TRELLIS_NEXT, _TRELLIS_OUT = _build_trellis(_DEFAULT_CONV)


def conv_decode_terminated(
    coded_bits: np.ndarray,
    *,
    cfg: ConvCodeConfig = _DEFAULT_CONV,
    drop_tail: bool = True,
) -> np.ndarray:
    """Hard-decision Viterbi decoder for terminated convolutional code.

    Expects the encoder used `terminate=True` and `tail_biting=False`.
    """
    coded_bits = np.asarray(coded_bits, dtype=np.uint8)
    if coded_bits.size % 3 != 0:
        coded_bits = coded_bits[: coded_bits.size - (coded_bits.size % 3)]

    m = cfg.memory
    n_states = cfg.n_states
    n_steps = coded_bits.size // 3

    # Path metrics
    INF = 1_000_000_000
    metrics = np.full(n_states, INF, dtype=np.int32)
    metrics[0] = 0

    # Store predecessors for traceback
    prev_state = np.empty((n_steps, n_states), dtype=np.int16)

    # Vectorized predecessor mapping for this trellis representation:
    states = np.arange(n_states, dtype=np.int32)
    u_for_state = (states >> (m - 1)) & 1
    p0 = ((states & ((1 << (m - 1)) - 1)) << 1)  # LSB = 0
    p1 = p0 | 1

    # Main Viterbi recursion
    for t in range(n_steps):
        y0 = int(coded_bits[3 * t])
        y1 = int(coded_bits[3 * t + 1])
        y2 = int(coded_bits[3 * t + 2])

        # expected outputs for p0 and p1 transitions
        out0 = _TRELLIS_OUT[p0, u_for_state]  # (64,3)
        out1 = _TRELLIS_OUT[p1, u_for_state]

        dist0 = (out0[:, 0] ^ y0) + (out0[:, 1] ^ y1) + (out0[:, 2] ^ y2)
        dist1 = (out1[:, 0] ^ y0) + (out1[:, 1] ^ y1) + (out1[:, 2] ^ y2)

        cand0 = metrics[p0] + dist0
        cand1 = metrics[p1] + dist1

        take1 = cand1 < cand0
        metrics = np.where(take1, cand1, cand0).astype(np.int32)
        prev_state[t, :] = np.where(take1, p1, p0).astype(np.int16)

    # Terminated trellis: end state is 0
    state = 0
    u_hat = np.empty(n_steps, dtype=np.uint8)
    for t in range(n_steps - 1, -1, -1):
        # input bit equals MSB of current state
        u_hat[t] = (state >> (m - 1)) & 1
        state = int(prev_state[t, state])

    if drop_tail and n_steps >= m:
        return u_hat[:-m].copy()
    return u_hat
