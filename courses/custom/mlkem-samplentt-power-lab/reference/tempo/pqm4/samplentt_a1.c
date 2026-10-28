/********************************************************************************
 * Project: Tempo                                                               *
 *                                                                              *
 * Name: Algorithm A1                                                           *
 * Description: CT rejection sampling, functionally equivalent to Algorithm A0  *
 ********************************************************************************/

#include "samplentt.h"
#include "params.h"
#include "fips202.h"

#define lt_1mask_16(x,y) (uint16_t)((((int16_t) x) - ((int16_t) y)) >> 15)    // 0xffffffff if  x < y, 0x00000000 otherwise
#define diff_1mask_16(x,y) (uint16_t)((0-((int16_t)((x^y) & 0x7fff))) >> 15)  // 0xffffffff if x != y, 0x00000000 otherwise
#define eq_1mask_16(x,y) (uint16_t)(~diff_1mask_16(x,y))                      // 0xffffffff if x == y, 0x00000000 otherwise

void algorithmA1(int16_t a[KYBER_N], const uint8_t extseed[KYBER_SYMBYTES + 2]) {
    uint8_t C[3];
    uint16_t ctr = 0;
    uint16_t d1, d2, acceptable_d1, acceptable_d2, flag, match, mask;

    shake128incctx state;
    shake128_inc_init(&state);
    shake128_inc_absorb(&state, extseed, KYBER_SYMBYTES + 2);
    shake128_inc_finalize(&state);
    
    for (unsigned int iter = 0; iter < MAX_ITER; iter++) {
        shake128_inc_squeeze(C, 3, &state);

        d1 = ((C[0] >> 0) | ((uint16_t)C[1] << 8)) & 0xFFF;
        d2 = ((C[1] >> 4) | ((uint16_t)C[2] << 4)) & 0xFFF;

        //acceptable_d1 = (uint16_t)(d1 < KYBER_Q);
        //acceptable_d2 = (uint16_t)(d2 < KYBER_Q);
        acceptable_d1 = lt_1mask_16(d1, KYBER_Q);
        acceptable_d2 = lt_1mask_16(d2, KYBER_Q);
        
        flag = 0;
        for (uint16_t j = 0; j < KYBER_N; j++) {
                //match = (uint16_t)(j == ctr);
                match = eq_1mask_16(j, ctr);
                mask = match * acceptable_d1;
                a[j] = (a[j] * (1 - mask)) + (d1 * mask);
                flag += mask;
        }
        ctr += flag;
        
        flag = 0;
        for (int j = 0; j < KYBER_N; j++) {
                //match = (uint16_t)(j == ctr);
                match = eq_1mask_16(j, ctr);
                mask = match * acceptable_d2;
                a[j] = (a[j] * (1 - mask)) + (d2 * mask);
                flag += mask;
        }
        ctr += flag;
    }
    shake128_inc_ctx_release(&state);
}
