SERIES ?= resolute
DESTDIR ?= install

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

install/cidata:
	mkdir -p $(DESTDIR)/cidata
	cp user-data $(DESTDIR)/cidata/
	cp meta-data $(DESTDIR)/cidata/
	touch $(DESTDIR)/cidata/vendor-data

install/dtb:
	rm -rf build
	mkdir build
	cd build && pull-ppa-debs --ppa=spacemit/k3  -a riscv64 linux-spacemit-generic $(SERIES)
	cd build && dpkg -x linux-modules*.deb linux-modules/
	mkdir -p $(DESTDIR)/dtb
	cp -r ./build/linux-modules/usr/lib/firmware/*-generic/device-tree/* \
	$(DESTDIR)/dtb
	rm -rf build

install/grub:
	rm -rf build
	mkdir build
	cd build && pull-ppa-debs --ppa=spacemit/k3 -a riscv64 grub2 $(SERIES)
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
	cd build && pull-ppa-debs --ppa=spacemit/k3 -a riscv64 opensbi-spacemit $(SERIES)
	cd build && dpkg -x opensbi-spacemit*.deb opensbi-spacemit/
	mkdir -p $(DESTDIR)/opensbi-spacemit
	cp build/opensbi-spacemit/usr/lib/riscv64-linux-gnu/opensbi/generic/fw_dynamic.itb $(DESTDIR)/opensbi-spacemit/
	rm -rf build

install/edk2:
	mkdir -p $(DESTDIR)/edk2
	cp edk2.itb $(DESTDIR)/edk2/edk2.itb

install/u-boot:
	rm -rf build
	mkdir build
	cd build && pull-ppa-debs --ppa=spacemit/k3 -a riscv64 u-boot-spacemit $(SERIES)
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
	cd build && pull-ppa-debs --ppa=spacemit/k3 -a riscv64 esos-spacemit $(SERIES)
	cd build && dpkg -x esos-spacemit*.deb esos-spacemit/
	mkdir -p $(DESTDIR)/esos
	cp build/esos-spacemit/usr/lib/riscv64-linux-gnu/esos/esos.itb $(DESTDIR)/esos/
	rm -rf build