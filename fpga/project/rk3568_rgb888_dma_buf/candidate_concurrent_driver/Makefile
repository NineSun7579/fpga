obj-m += pango_zc.o

# Supply the configured, prepared kernel build tree matching the RK3568 kernel.
KDIR ?= /lib/modules/$(shell uname -r)/build
ARCH ?= arm64
CROSS_COMPILE ?= aarch64-linux-gnu-

.PHONY: all clean
all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) ARCH=$(ARCH) CROSS_COMPILE=$(CROSS_COMPILE) modules
clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) ARCH=$(ARCH) CROSS_COMPILE=$(CROSS_COMPILE) clean
