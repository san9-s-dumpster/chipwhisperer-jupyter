#ifndef ALGORITHMS_H
#define ALGORITHMS_H

#include <stdint.h>
#include "config.h"

void algorithmA0(int16_t a[KYBER_N], const uint8_t seed[34]);
void algorithmA1(int16_t a[KYBER_N], const uint8_t seed[34]);
void algorithmB0(int16_t a[KYBER_N], const uint8_t seed[34]);
void algorithmC0(int16_t a[KYBER_N], const uint8_t seed[34]);
void algorithmC1(int16_t a[KYBER_N], const uint8_t seed[34]);
uint16_t reduce192(uint32_t x[6]);
uint16_t barrett_reduce32(uint32_t x);

#endif
