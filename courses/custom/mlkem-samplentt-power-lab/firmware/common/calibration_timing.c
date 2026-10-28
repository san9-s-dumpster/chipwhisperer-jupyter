/* SPDX-License-Identifier: GPL-3.0-or-later
 * Cortex-M4 calibration ONLY. Link --wrap instead of editing the sampler.
 * Stores first two SHAKE squeeze boundaries. No UART inside the trigger.
 * Wrapper, stores and code layout change timing: never use these traces to
 * train or evaluate the representative firmware's distinguisher.
 */
#include "calibration_timing.h"
#include "fips202.h"
#include "simpleserial.h"
#define REG32(a) (*(volatile uint32_t *)(a))
#define CYCCNT REG32(0xE0001004u)
static volatile uint32_t times[6];
static volatile uint32_t active;
void lab_timing_begin(void) {
    REG32(0xE000EDFCu) |= 1u << 24; /* DEMCR.TRCENA */
    REG32(0xE0001000u) |= 1u;       /* DWT_CTRL.CYCCNTENA */
    active = 0;
    for (unsigned i=0; i<6; ++i) times[i] = 0;
    CYCCNT = 0;
    active = 1;
}
void lab_timing_end(void) { times[4] = CYCCNT; active = 0; }
void __real_shake128_inc_squeeze(uint8_t *, size_t, shake128incctx *);
void __wrap_shake128_inc_squeeze(uint8_t *out, size_t n, shake128incctx *ctx) {
    uint32_t call = times[5];
    if (active && call < 2) times[2*call] = CYCCNT;
    __real_shake128_inc_squeeze(out, n, ctx);
    if (active) {
        if (call < 2) times[2*call+1] = CYCCNT;
        times[5] = call+1;
    }
}
uint8_t lab_timing_reply(uint8_t *ignored, uint8_t length) {
    (void)ignored;
    if (length || !times[4] || times[5] < 2) return 1;
    uint8_t out[24];
    for (unsigned i=0; i<6; ++i)
        for (unsigned j=0; j<4; ++j) out[4*i+j] = times[i] >> (8*j);
    simpleserial_put('t', sizeof(out), out);
    return 0;
}
