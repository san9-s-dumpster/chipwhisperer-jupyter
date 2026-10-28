ifndef FIRMWAREPATH
$(error Set FIRMWAREPATH to the absolute ChipWhisperer firmware/mcu directory)
endif
LAB_ROOT := $(abspath ../..)
TEMPO := $(LAB_ROOT)/reference/tempo
TARGET = samplentt-fls
CRYPTO_TARGET = NONE
SRC += main.c algorithm_a1.c fips202.c
VPATH += :$(LAB_ROOT)/firmware/common:$(TEMPO)/src
EXTRAINCDIRS += $(TEMPO)/include
CDEFS += -DLAB_FLS=1
include $(FIRMWAREPATH)/Makefile.inc
