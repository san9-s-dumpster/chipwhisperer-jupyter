/* SPDX-License-Identifier: GPL-3.0-or-later
 * Single-polynomial lab adapter. Upstream sampler and SHAKE code are unchanged.
 * SimpleSerial v1.1: p = rho[32] || x || y; r = SHA3-256(LE16(output[256])).
 * Application identity uses i; v is reserved by the SimpleSerial library.
 */
#include "hal.h"
#include "simpleserial.h"
#include "algorithms.h"
#include "fips202.h"
#include <stdint.h>
#include <string.h>
#ifndef LAB_CALIBRATION
#define LAB_CALIBRATION 0
#endif
#if LAB_CALIBRATION
#include "calibration_timing.h"
#endif

#if SS_VER != SS_VER_1_1
#error "This adapter implements SimpleSerial v1.1 only"
#endif
#ifndef LAB_FLS
#error "Build through firmware/variable_time or firmware/fls"
#endif

static int16_t polynomial[256];
static uint8_t encoded[512];
static uint8_t digest[32];

static uint8_t sample(uint8_t *input, uint8_t length)
{
    if (length != 34) return 1;
    /* A1 reads each existing coefficient. Do not move this into the trigger. */
    memset(polynomial, 0, sizeof(polynomial));
#if LAB_CALIBRATION
    lab_timing_begin();
#endif
    trigger_high();
#if LAB_FLS
    algorithmA1(polynomial, input);
#else
    algorithmA0(polynomial, input);
#endif
    trigger_low();
#if LAB_CALIBRATION
    lab_timing_end();
#endif
    for (unsigned int i = 0; i < 256; ++i) {
        encoded[2*i] = (uint16_t)polynomial[i] & 255;
        encoded[2*i+1] = (uint16_t)polynomial[i] >> 8;
    }
    sha3_256(digest, encoded, sizeof(encoded));
    simpleserial_put('r', sizeof(digest), digest);
    return 0;
}

static uint8_t identity(uint8_t *ignored, uint8_t length)
{
    (void)ignored;
    if (length != 0) return 1;
    uint8_t info[21] = {LAB_FLS | (LAB_CALIBRATION ? 0x80 : 0),
        0xfd,0x72,0x83,0x4b,0xd7,0x89,0xc6,0x44,0xb5,0x2f,
        0xe0,0xd6,0x2b,0x2f,0xa3,0xb9,0xf3,0x4d,0xfa,0xec};
    simpleserial_put('i', sizeof(info), info);
    return 0;
}

int main(void)
{
    platform_init();
    init_uart();
    trigger_setup();
    simpleserial_init();
    simpleserial_addcmd('p', 34, sample);
    simpleserial_addcmd('i', 0, identity);
#if LAB_CALIBRATION
    simpleserial_addcmd('t', 0, lab_timing_reply);
#endif
    while (1) simpleserial_get();
}
