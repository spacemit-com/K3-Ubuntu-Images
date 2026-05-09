SpacemiT K3 gadget
==================

Build a UEFI-bootable Ubuntu RISC-V preinstalled image for the SpacemiT K3
Pico-ITX board and flash it through fastboot.

`中文文档 <README.zh.rst>`_

The resulting image lays out a single GPT disk with raw firmware partitions
(``env``, ``bootinfo``, ``fsbl``, ``esos``, ``opensbi``, ``uboot``), an
EFI System Partition, a ``CIDATA`` cloud-init partition and an ``ext4``
``writable`` rootfs.

Prebuilt images
---------------

If you only want to flash a board, grab the latest
``ubuntu-26.04-preinstalled-desktop-riscv64.img.zst`` (and its checksum)
from the project's GitHub Releases, then jump to `Flash a board`_.

Flash a board
-------------

Hardware: put the SpacemiT K3 Pico-ITX board into flash mode.

Install dependencies on an Ubuntu (22.04 or later) host:

.. code-block:: bash

    sudo apt-get update
    sudo apt-get install git ubuntu-dev-tools fastboot
    git clone https://github.com/spacemit-com/K3-Ubuntu-Images.git gadget
    cd gadget

Flash in one step:

.. code-block:: bash

    make IMG=/path/to/ubuntu-26.04-preinstalled-desktop-riscv64.img.zst all

Run the steps manually:

.. code-block:: bash

    # 1. Extract partitions from the image into ./temp
    python3 image_flash.py \
        --img path/to/ubuntu-26.04-preinstalled-desktop-riscv64.img \
        --partition partition_universal.json

    # 2. Place u-boot.itb (obtained from the PPA) into ./temp.
    #    The BootROM loads it into RAM over USB; it runs in RAM as a
    #    temporary fastboot server and is never written to any storage partition.
    cp /path/to/u-boot.itb temp/u-boot.itb

    # 3. Flash
    sudo python3 image_flash.py --fastboot fastboot.yaml

First boot
----------

Default credentials: ``ubuntu`` / ``ubuntu``.

The image ships ``ubuntu-desktop`` and Chromium.

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

    git clone https://github.com/spacemit-com/K3-Ubuntu-Images.git gadget
    cd gadget
    make image          # clean build via ubuntu-image

Useful build variants:

.. code-block:: bash

    make image-debug    # clean build with --debug

The image is produced at::

    workdir/ubuntu-26.04-preinstalled-desktop-riscv64.img

Runtime boot chain
------------------

::

                                ┌→ ESOS (management core, runs independently)
    BootROM → FSBL (U-Boot SPL) ┤
                                └→ OpenSBI → EDK2 UEFI → GRUB → Linux

Each stage in detail:

- **BootROM** reads the ``bootinfo`` partition to locate and verify the FSBL,
  then transfers control to it.
- **FSBL** (``fsbl`` partition, U-Boot SPL) initialises clocks, DRAM and
  peripheral hardware, then launches two payloads in parallel:

  - **ESOS** (``esos`` partition) — the Energy Service OS, a multi-task
    RTOS designed for power management, running on a dedicated management
    core independently of the application core boot flow.
  - **OpenSBI** (``opensbi`` partition) — sets up the SBI runtime on the
    application core and boots the next-stage payload — EDK2.
- **EDK2 UEFI** (``uboot`` partition, stores ``edk2.itb``) provides the full
  UEFI environment.  Despite the partition name inherited from the U-Boot boot
  layout, the runtime payload is the EDK2 firmware — not U-Boot.
- **GRUB** is loaded by EDK2 from the ESP as ``EFI/boot/bootriscv64.efi``.  A
  stub ``grub.cfg`` on the ESP redirects GRUB to ``/boot/grub/grub.cfg`` on
  the ``writable`` partition.
- **Linux** is booted by GRUB with the parameters defined in
  ``/boot/grub/grub.cfg``.

Role of u-boot.itb
------------------

``u-boot.itb`` is **not** part of the runtime boot chain.  It is used solely
as a temporary flashing service:

1. The SpacemiT K3 BootROM, when in USB-download mode, accepts a FIT image
   over USB and loads it entirely into RAM.
2. The host uploads ``u-boot.itb`` — a full U-Boot build containing a fastboot
   server — into the board's RAM.
3. U-Boot runs in RAM and exposes the fastboot protocol to the host.
4. The host then drives ``fastboot`` to write all GPT/NOR partition images to
   the target storage.
5. On the next power-cycle the board boots from the freshly written partitions
   using the runtime chain above; ``u-boot.itb`` is never persisted to storage.

GRUB initialisation
-------------------

The image uses a two-phase GRUB setup.

**Pre-installed (image-time):**

- The ESP is populated with a pre-built ``grubriscv64.efi`` and a minimal stub
  ``grub.cfg`` (``gadget.in/grub.cfg``) that redirects GRUB to
  ``/boot/grub/grub.cfg`` on the ``writable`` partition.
- The ``writable`` rootfs ships with a pre-generated ``/boot/grub/grub.cfg``
  (sourced from ``grub.cfg`` in this repository).  This is sufficient to boot
  the system on the very first power-on.

**First-boot (runtime):**

On the first boot a cloud-init job runs:

- ``grub-install`` — installs the GRUB EFI binary for the running system and
  registers a UEFI boot entry in NVRAM, replacing the generic pre-installed
  stub.
- ``update-grub`` — regenerates ``/boot/grub/grub.cfg`` from the installed
  kernels, ``/etc/grub.d/`` templates and ``/etc/default/grub`` settings,
  replacing the image-time pre-generated file.

Subsequent kernel upgrades automatically trigger ``update-grub`` to keep the
boot menu up to date.

Repository layout
-----------------

::

    image-definition.yaml       ubuntu-image classic build definition
    gadget.in/                  gadget source (partitions + firmware)
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
    partition_universal.json    GPT partition table (UFS/SSD)
    partition_4M.json           NOR partition table
