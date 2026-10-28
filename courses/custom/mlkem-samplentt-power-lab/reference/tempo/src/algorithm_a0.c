/********************************************************************************
 * Project: Tempo                                                               *
 *                                                                              *
 * Name: Algorithm A0                                                           *
 * Description: VT rejection sampling [Algorithm 7, FIPS 203]                   *
 ********************************************************************************/

#include "algorithms.h"
#include "config.h"
#include "fips202.h"

void algorithmA0(int16_t a[KYBER_N], const uint8_t extseed[KYBER_SYMBYTES + 2]) {
    uint8_t C[3];
    unsigned int j = 0, iter = 0;

    shake128incctx state;
    shake128_inc_init(&state);
    shake128_inc_absorb(&state, extseed, KYBER_SYMBYTES + 2);
    shake128_inc_finalize(&state);
    
    while (j < KYBER_N && iter < MAX_ITER) {
        shake128_inc_squeeze(C, 3, &state);
        
        uint16_t d1 = ((C[0] >> 0) | ((uint16_t)C[1] << 8)) & 0xFFF;
        uint16_t d2 = ((C[1] >> 4) | ((uint16_t)C[2] << 4)) & 0xFFF;

        if (d1 < KYBER_Q) a[j++] = d1;
        if (d2 < KYBER_Q && j < KYBER_N) a[j++] = d2;

        iter++;
    }
    shake128_inc_ctx_release(&state);
}
