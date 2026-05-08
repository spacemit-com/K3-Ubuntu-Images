SpacemiT K3 gadget
==================

Build a UEFI-bootable Ubuntu RISC-V preinstalled image for the SpacemiT K3
Pico-ITX board and flash it through fastboot.

The resulting image lays out a single GPT disk with raw firmware partitions
(``env``, ``bootinfo``, ``fsbl``, ``esos``, ``opensbi``, ``uboot``), an
EFI System Partition, a ``CIDATA`` cloud-init partition and an ``ext4``
``writable`` rootfs.  Boot chain: BootROM → FSBL → OpenSBI → EDK2 (UEFI) → GRUB → Linux.
Only U-Boot SPL stages (FSBL / bootinfo) are placed on disk; the full
u-boot.itb body is not part of the runtime boot chain.

Prebuilt images
---------------

If you only want to flash a board, grab the latest
``ubuntu-26.04-preinstalled-server-riscv64.img`` (and its checksum) from the
project's GitHub release page or mirror, then jump to `Flash a board`_.

Build the image
---------------

Install build dependencies on an Ubuntu host:

.. code-block:: bash

    sudo apt-get update
    sudo apt-get install git snapd qemu-user-static ubuntu-dev-tools \
                         python3-yaml fastboot
    sudo snap install --classic ubuntu-image

Clone and build:

.. code-block:: bash

    git clone <this-repo> gadget
    cd gadget
    make image          # clean build via ubuntu-image

Useful build variants:

.. code-block:: bash

    make image-debug    # clean build with --debug
    make image-init     # stop before manual customization (-u perform_manual_customization)
    make image-continue # resume the previous workdir (-r)

The image is produced at::

    workdir/ubuntu-26.04-preinstalled-server-riscv64.img

Flash a board
-------------

Hardware: SpacemiT K3 board in fastboot/USB-download mode, host running
``fastboot``.

The flash workflow has two phases driven by ``image_flash.py``:

1. **extract** — split the GPT image into per-partition files under ``./temp/``
2. **flash** — drive the BootROM/U-Boot/fastboot sequence described by
   ``fastboot.yaml`` and write each partition

End-to-end with the bundled Makefile:

.. code-block:: bash

    # Use the image you just built
    make all

    # Or use a downloaded image
    make IMG=/path/to/ubuntu-26.04-preinstalled-server-riscv64.img all

The Makefile assumes the U-Boot FIT lives under
``workdir/scratch/gadget/install/u-boot-spacemit/u-boot.itb`` (true after a
local ``make image``).  When flashing a downloaded image, if that path does
not exist ``make flash`` will automatically fetch ``u-boot-spacemit`` from the
PPA and extract ``u-boot.itb``; no manual step is required.

To use a specific ``u-boot.itb``, override ``UBOOT_ITB`` on the command line::

    make UBOOT_ITB=/path/to/u-boot.itb flash

Run the steps manually:

.. code-block:: bash

    # 1. Extract partitions from the image into ./temp
    python3 image_flash.py \
        --img path/to/ubuntu-26.04-preinstalled-server-riscv64.img \
        --partition partition_universal.json

    # 2. Drop u-boot.itb into ./temp (required by the fastboot BootROM staging
    #    step; it is not written to the runtime flash partitions)
    cp /path/to/u-boot.itb temp/u-boot.itb

    # 3. Flash
    sudo python3 image_flash.py --fastboot fastboot.yaml

Selective flashing
~~~~~~~~~~~~~~~~~~

For development and debugging, ``--only`` and ``--skip`` filter which
partitions are touched (mutually exclusive, comma-separated names):

.. code-block:: bash

    # Only re-flash the EFI System Partition
    sudo python3 image_flash.py --fastboot fastboot.yaml --only esp

    # Re-flash everything except the rootfs (much faster iteration)
    sudo python3 image_flash.py --fastboot fastboot.yaml --skip writable

    # Same flags also work at extraction time
    python3 image_flash.py --img <img> --partition partition_universal.json --only esp

When ``--only`` selects partitions that are not present in a given partition
table, the corresponding fastboot phase is skipped automatically (e.g.
``--only esp`` skips the MTD/NOR phase entirely and stays in GPT context).

First boot
----------

Login as ``ubuntu`` / ``ubuntu``.  The image ships ``ubuntu-desktop`` and the
PowerVR GPU userspace。

Repository layout
-----------------

::

    image-definition.yaml       ubuntu-image classic build definition
    gadget.in/                  gadget snap source (partitions + firmware)
        Makefile                pulls firmware (.deb) from spacemit/k3 PPA
        gadget.yaml             GPT layout
        edk2.itb                EDK2 UEFI FIT (vendored binary)
        grub.cfg                ESP grub stub
        user-data / meta-data   cloud-init NoCloud
    grub.cfg                    rootfs /boot/grub/grub.cfg (UEFI menu)
    grub.d/                     /etc/default/grub.d snippets
    setup-scripts.sh            in-image customization (apt upgrade)
    spacemit-ppa-preference     APT pin for spacemit/k3 PPA
    Makefile                    image build + flash workflow entry points
    image_flash.py              extract & fastboot driver
    fastboot.yaml               fastboot flash flow
    partition_universal.json    GPT partition table (block device)
    partition_4M.json           MTD/NOR partition table (boot SPI)
