SERIES ?= resolute
DESTDIR ?= install
FLAVOR ?= k3-6.12

all:
	mkdir -p $(DESTDIR)
	make install/cidata
	make install/dtb
	make install/grub
	make meta

meta:
	mkdir -p $(DESTDIR)/meta
	cp gadget.yaml $(DESTDIR)/meta/

install/cidata:
	mkdir -p $(DESTDIR)/cidata
	cp user-data $(DESTDIR)/cidata/
	cp meta-data $(DESTDIR)/cidata/
	touch $(DESTDIR)/cidata/vendor-data

install/dtb:
	rm -rf build
	mkdir build
	cd build && \
	pull-ppa-debs --ppa=esmil/ppa -a riscv64 linux-$(FLAVOR) $(SERIES)
	cd build && dpkg -x linux-modules*.deb linux-modules/
	mkdir -p $(DESTDIR)/dtb
	cp -r ./build/linux-modules/usr/lib/firmware/*-$(FLAVOR)/device-tree/* \
	$(DESTDIR)/dtb
	rm -rf build

install/grub:
	rm -rf build
	mkdir build
	cd build && pull-lp-debs -a riscv64 grub2 $(SERIES)
	cd build && dpkg -x grub-efi-riscv64-bin*.deb grub/
	mkdir -p $(DESTDIR)/grub
	cp ./build/grub/usr/lib/grub/riscv64-efi/monolithic/grubriscv64.efi \
	$(DESTDIR)/grub/
	cp grub.cfg $(DESTDIR)/grub/
	rm -rf build

image:
	sudo rm -rf workdir
	sudo ubuntu-image --workdir workdir classic image-definition.yaml

image-debug:
	sudo rm -rf workdir
	sudo ubuntu-image --workdir workdir --debug classic \
	image-definition.yaml
