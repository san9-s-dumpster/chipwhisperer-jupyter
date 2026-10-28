ifndef FIRMWAREPATH
$(error Set FIRMWAREPATH to the absolute ChipWhisperer firmware/mcu directory)
endif
LAB_ROOT := $(abspath ../..)
TEMPO := $(LAB_ROOT)/reference/tempo
TARGET = samplentt-variable_time
CRYPTO_TARGET = NONE
SRC += main.c algorithm_a0.c fips202.c
VPATH += :$(LAB_ROOT)/firmware/common:$(TEMPO)/src
EXTRAINCDIRS += $(TEMPO)/include
CDEFS += -DLAB_FLS=0
include $(FIRMWAREPATH)/Makefile.inc
