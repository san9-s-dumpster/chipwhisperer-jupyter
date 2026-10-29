ifndef FIRMWAREPATH
$(error Set FIRMWAREPATH to the absolute ChipWhisperer firmware/mcu directory)
endif
LAB_ROOT := $(abspath ../..)
TEMPO := $(LAB_ROOT)/reference/tempo
TARGET = samplentt-fls_calibration
CRYPTO_TARGET = NONE
SRC += main.c calibration_timing.c algorithm_a1.c fips202.c
VPATH += :$(LAB_ROOT)/firmware/common:$(TEMPO)/src
EXTRAINCDIRS += $(TEMPO)/include $(LAB_ROOT)/firmware/common
CDEFS += -DLAB_FLS=1 -DLAB_CALIBRATION=1
LDFLAGS += -Wl,--wrap=shake128_inc_squeeze
include $(FIRMWAREPATH)/Makefile.inc
