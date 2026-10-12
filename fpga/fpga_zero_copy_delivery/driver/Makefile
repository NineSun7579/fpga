ifneq ($(KERNELRELEASE),)
obj-m := pango_zc.o
ccflags-y += -Werror
else
KDIR ?= /usr/src/linux-headers-6.1-rockchip
.PHONY: all clean
all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) modules
clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) clean
endif
