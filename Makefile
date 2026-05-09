# Makefile - build Ubuntu UEFI RISC-V image and flash to nor+ufs/ssd via fastboot
#
# Image build targets (ubuntu-image):
#   make image           # clean build
#   make image-debug     # clean build with --debug
#   make image-init      # stop before manual customization (-u perform_manual_customization)
#   make image-continue  # resume previous workdir (-r)
#   make compress        # compress $(IMG) to $(IMG).zst with zstd
#
# Flash workflow targets (image_flash.py):
#   make extract         # extract partitions from $(IMG) into ./$(TEMP_DIR)
#   make flash           # run fastboot flow (assumes ./$(TEMP_DIR) populated)
#   make all             # extract + flash
#   make clean           # remove ./$(TEMP_DIR)
#   make IMG=other.img extract
#
# Requirements:
#   - ubuntu-image (for image-* targets)
#   - python3, pyyaml, fastboot in PATH (for extract/flash targets)
#   - u-boot.itb present in CWD before flash (U-Boot FIT, not contained in the .img, needed for fastboot flash although not actually flashed to the device)

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

PYTHON       ?= python3
SCRIPT       ?= image_flash.py
WORKDIR      ?= workdir
IMG_DEF      ?= image-definition.yaml
IMG          ?= $(WORKDIR)/ubuntu-26.04-preinstalled-desktop-riscv64.img
PARTITION    ?= partition_universal.json
FASTBOOT     ?= fastboot.yaml
TEMP_DIR     ?= temp

GADGET_INSTALL ?= $(WORKDIR)/scratch/gadget/install
UBOOT_ITB      ?= $(WORKDIR)/scratch/gadget/install/u-boot-spacemit/u-boot.itb

UBUNTU_IMAGE       ?= sudo ubuntu-image
UBUNTU_IMAGE_FLAGS ?= --sector-size=4096 --workdir $(WORKDIR)

.PHONY: help all image image-debug image-init image-continue compress \
	extract flash check clean

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

help:
	@echo "Image build targets:"
	@echo "  image            - clean build"
	@echo "  image-debug      - clean build with --debug"
	@echo "  image-init       - stop before manual customization"
	@echo "  image-continue   - resume previous workdir (-r)"
	@echo "  compress         - compress \$$(IMG) to \$$(IMG).zst (zstd)"
	@echo ""
	@echo "Flash workflow targets:"
	@echo "  extract          - extract partitions from \$$(IMG) into ./$(TEMP_DIR)"
	@echo "  flash            - run fastboot flow using ./$(TEMP_DIR)"
	@echo "  all              - extract then flash"
	@echo "  clean            - remove ./$(TEMP_DIR)"
	@echo ""
	@echo "Variables (override on command line):"
	@echo "  IMG=$(IMG)"
	@echo "  PARTITION=$(PARTITION)"
	@echo "  FASTBOOT=$(FASTBOOT)"
	@echo "  WORKDIR=$(WORKDIR)"

# ---------------------------------------------------------------------------
# Image build (ubuntu-image)
# ---------------------------------------------------------------------------

image:
	sudo rm -rf $(WORKDIR)
	$(UBUNTU_IMAGE) --workdir $(WORKDIR) classic $(IMG_DEF)

image-debug:
	sudo rm -rf $(WORKDIR)
	$(UBUNTU_IMAGE) $(UBUNTU_IMAGE_FLAGS) --debug classic $(IMG_DEF)

image-init:
	$(UBUNTU_IMAGE) $(UBUNTU_IMAGE_FLAGS) --debug \
	    -u perform_manual_customization classic $(IMG_DEF)

image-continue:
	$(UBUNTU_IMAGE) $(UBUNTU_IMAGE_FLAGS) --debug -r classic $(IMG_DEF)

compress: $(IMG)
	sudo zstd -T0 -v --keep $(IMG)

# ---------------------------------------------------------------------------
# Flash workflow (image_flash.py + fastboot)
# ---------------------------------------------------------------------------

all: extract flash

extract: $(IMG) $(PARTITION)
	$(PYTHON) $(SCRIPT) --img $(IMG) --partition $(PARTITION)

flash: check
	sudo $(PYTHON) $(SCRIPT) --fastboot $(FASTBOOT)

check:
	@test -d $(TEMP_DIR) || { \
	    echo "ERROR: ./$(TEMP_DIR) not found. Run 'make extract' first."; exit 1; }
	@if [ ! -f "$(UBOOT_ITB)" ]; then \
	    echo "INFO: u-boot.itb not found, fetching from PPA..."; \
	    $(MAKE) -C gadget.in install/u-boot DESTDIR=../$(GADGET_INSTALL); \
	fi
	@cp $(UBOOT_ITB) $(TEMP_DIR)/u-boot.itb
	@command -v fastboot >/dev/null || { \
	    echo "ERROR: fastboot not in PATH."; exit 1; }

clean:
	rm -rf $(TEMP_DIR)
