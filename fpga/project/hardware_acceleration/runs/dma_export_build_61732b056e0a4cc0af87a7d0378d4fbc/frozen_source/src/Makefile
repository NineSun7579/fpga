# Offline candidate only. Never resolves /lib/modules/.../build implicitly.
ifneq ($(KERNELRELEASE),)
obj-m += pango_dma_candidate.o
else
KDIR ?=
.PHONY: all clean
all:
	@test -n "$(KDIR)" || (echo 'Set KDIR to the frozen generated 6.1.99 header root'; exit 1)
	$(MAKE) -C "$(KDIR)" M="$(CURDIR)" modules
clean:
	@test -n "$(KDIR)" || (echo 'Set KDIR explicitly'; exit 1)
	$(MAKE) -C "$(KDIR)" M="$(CURDIR)" clean
endif
