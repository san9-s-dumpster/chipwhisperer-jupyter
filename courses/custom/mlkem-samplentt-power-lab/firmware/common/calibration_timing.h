/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdint.h>
void lab_timing_begin(void);
void lab_timing_end(void);
uint8_t lab_timing_reply(uint8_t *ignored, uint8_t length);
