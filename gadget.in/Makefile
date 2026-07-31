SERIES ?= resolute
DESTDIR ?= install

# Pull a package, picking the PPA via a fast LP API probe FIRST (check-pkg.py):
#   - source Published in k3-preview -> 5x retry k3-preview (the new BSP)
#   - only in k3 (grub2, spacemit-ec-firmware) -> pull k3 directly, skip 5x
#     wasted k3-preview retries (was 150s+ of 503s on packages not even there;
#     #22189 ec failure was partly this).
# 5x exponential backoff (10/20/30/40/50s) on the chosen PPA handles 503 spells
# without the old `{ k3-preview } || { k3 } && break` bug (first 503 -> k3 stale
# old version; #22196 got u-boot 1.0.2 May-28 FSBL instead of 1.0.5 Jul-24).
# Only after 5x does it try the OTHER PPA once (warns may be older).
# NOTE: no `timeout` on pull-ppa-debs — LP has SLOW-download spells (linux-image
# hundreds of MB; LP 200 but bandwidth drops). A timeout kills the slow transfer,
# retry from scratch (no resume) -> never completes -> build_gadget_tree stalls
# looking "stuck" (#22191/#22192/#22194 mis-canceled). 5x fires only on FAILURE
# (503/error), not slow-but-live. ubuntu-image buffers make stdout (use
# `make image-debug`), so trace shows nothing during slow download — NOT a hang.
pull_pkg = \
  PPA=$$(python3 ../check-pkg.py $(1) 2>/dev/null || echo k3-preview); \
  [ "$$PPA" = "none" ] && PPA=k3-preview; \
  echo "==> pull_pkg: $(1) -> $$PPA" >&2; \
  for i in 1 2 3 4 5; do \
    rm -f *.deb 2>/dev/null; \
    pull-ppa-debs --ppa=spacemit/$$PPA -a riscv64 $(1) $(SERIES) && ls *.deb >/dev/null 2>&1 && break; \
    echo "==> pull_pkg: $(1) $$PPA attempt $$i failed (Launchpad 503?), retrying in $$((i*10))s..." >&2; sleep $$((i*10)); \
  done; \
  ls *.deb >/dev/null 2>&1 || { \
    OTHER=k3-preview; [ "$$PPA" = "k3-preview" ] && OTHER=k3; \
    echo "==> pull_pkg: $(1) $$PPA exhausted after 5x, trying $$OTHER (WARNING: may be older)" >&2; \
    rm -f *.deb 2>/dev/null; \
    pull-ppa-debs --ppa=spacemit/$$OTHER -a riscv64 $(1) $(SERIES) && ls *.deb >/dev/null 2>&1; \
  }

all:
	mkdir -p $(DESTDIR)
	make install/cidata
	make install/dtb
	make install/grub
	make meta
	make install/opensbi
	make install/u-boot
	make install/esos
	make install/edk2
	make install/ec

install/cidata:
	mkdir -p $(DESTDIR)/cidata
	cp user-data $(DESTDIR)/cidata/
	cp meta-data $(DESTDIR)/cidata/
	touch $(DESTDIR)/cidata/vendor-data

install/dtb:
	rm -rf build
	mkdir build
	cd build && $(call pull_pkg,linux-spacemit-generic)
	cd build && dpkg -x linux-modules*.deb linux-modules/
	mkdir -p $(DESTDIR)/dtb
	cp -r ./build/linux-modules/usr/lib/firmware/*-generic/device-tree/* \
	$(DESTDIR)/dtb
	rm -rf build

install/grub:
	rm -rf build
	mkdir build
	cd build && $(call pull_pkg,grub2)
	cd build && dpkg -x grub-efi-riscv64-unsigned*.deb grub/
	mkdir -p $(DESTDIR)/grub
	cp ./build/grub/usr/lib/grub/riscv64-efi/monolithic/grubriscv64.efi \
	$(DESTDIR)/grub/
	cp grub.cfg $(DESTDIR)/grub/
	rm -rf build

meta:
	mkdir -p $(DESTDIR)/meta
	cp gadget.yaml $(DESTDIR)/meta/

install/opensbi:
	rm -rf build
	mkdir build
	cd build && $(call pull_pkg,opensbi-spacemit)
	cd build && dpkg -x opensbi-spacemit*.deb opensbi-spacemit/
	mkdir -p $(DESTDIR)/opensbi-spacemit
	cp build/opensbi-spacemit/usr/lib/riscv64-linux-gnu/opensbi/generic/fw_dynamic.itb $(DESTDIR)/opensbi-spacemit/
	rm -rf build

install/edk2:
	rm -rf build
	mkdir build
	cd build && $(call pull_pkg,edk2-spacemit)
	cd build && dpkg -x edk2-spacemit*.deb edk2-spacemit/
	mkdir -p $(DESTDIR)/edk2
	cp build/edk2-spacemit/usr/lib/uefi/spacemit/edk2.itb $(DESTDIR)/edk2/
	rm -rf build

install/u-boot:
	rm -rf build
	mkdir build
	cd build && $(call pull_pkg,u-boot-spacemit)
	cd build && dpkg -x u-boot-spacemit*.deb u-boot-spacemit/
	mkdir -p $(DESTDIR)/u-boot-spacemit
	cp build/u-boot-spacemit/usr/lib/u-boot/spacemit/bootinfo_block.bin $(DESTDIR)/u-boot-spacemit/
	cp build/u-boot-spacemit/usr/lib/u-boot/spacemit/bootinfo_spinand.bin $(DESTDIR)/u-boot-spacemit/
	cp build/u-boot-spacemit/usr/lib/u-boot/spacemit/bootinfo_spinor.bin $(DESTDIR)/u-boot-spacemit/
	cp build/u-boot-spacemit/usr/lib/u-boot/spacemit/env.bin $(DESTDIR)/u-boot-spacemit/
	cp build/u-boot-spacemit/usr/lib/u-boot/spacemit/u-boot.itb $(DESTDIR)/u-boot-spacemit/
	cp build/u-boot-spacemit/usr/lib/u-boot/spacemit/FSBL.bin $(DESTDIR)/u-boot-spacemit/
	rm -rf build

install/esos:
	rm -rf build
	mkdir build
	cd build && $(call pull_pkg,esos-spacemit)
	cd build && dpkg -x esos-spacemit*.deb esos-spacemit/
	mkdir -p $(DESTDIR)/esos
	cp build/esos-spacemit/usr/lib/riscv64-linux-gnu/esos/esos.itb $(DESTDIR)/esos/
	rm -rf build

install/ec:
	rm -rf build
	mkdir build
	cd build && $(call pull_pkg,spacemit-ec-firmware)
	cd build && dpkg -x spacemit-ec-firmware*.deb spacemit-ec-firmware/
	mkdir -p $(DESTDIR)/ec
	cp build/spacemit-ec-firmware/lib/firmware/*/ec.bin $(DESTDIR)/ec/
	rm -rf build