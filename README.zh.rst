SpacemiT K3 gadget
==================

为 SpacemiT K3 Pico-ITX 开发板构建支持 UEFI 启动的 Ubuntu RISC-V 预装镜像，
并通过 fastboot 完成烧写。

生成的镜像以单块 GPT 磁盘布局，包含原始固件分区
（``env``、``bootinfo``、``fsbl``、``esos``、``opensbi``、``uboot``）、
EFI 系统分区、``CIDATA`` cloud-init 分区以及 ``ext4`` 格式的 ``writable`` 根文件系统。

启动链：BootROM → FSBL → OpenSBI → EDK2 (UEFI) → GRUB → Linux

说明：磁盘上只存放 U-Boot SPL 阶段产物（FSBL / bootinfo），完整的 u-boot.itb
本体不参与运行时启动链；u-boot.itb 仅在 fastboot 烧写时由 BootROM 暂存使用。

预构建镜像
----------

如果只需要烧写开发板，从项目 GitHub Releases 或镜像站获取最新的
``ubuntu-26.04-preinstalled-server-riscv64.img``（及其校验文件），
然后直接跳至 `烧写开发板`_ 章节。

构建镜像
--------

在 Ubuntu 主机上安装构建依赖：

.. code-block:: bash

    sudo apt-get update
    sudo apt-get install git snapd qemu-user-static ubuntu-dev-tools \
                         python3-yaml fastboot
    sudo snap install --classic ubuntu-image

克隆并构建：

.. code-block:: bash

    git clone <本仓库地址> gadget
    cd gadget
    make image          # 通过 ubuntu-image 进行全量构建

可用构建变体：

.. code-block:: bash

    make image-debug    # 带 --debug 的全量构建
    make image-init     # 在手动定制前停止（-u perform_manual_customization）
    make image-continue # 继续上次中断的工作目录（-r）

构建产物路径::

    workdir/ubuntu-26.04-preinstalled-server-riscv64.img

烧写开发板
----------

硬件准备：将 SpacemiT K3 Pico-ITX 开发板切换至 fastboot / USB 下载模式，
主机已安装 ``fastboot``。

烧写流程由 ``image_flash.py`` 驱动，分两个阶段：

1. **extract（提取）** — 将 GPT 镜像按分区拆分至 ``./temp/`` 目录
2. **flash（烧写）** — 按照 ``fastboot.yaml`` 描述的 BootROM/fastboot 序列逐分区写入

使用 Makefile 一键完成：

.. code-block:: bash

    # 使用本地刚构建的镜像
    make all

    # 使用下载的镜像
    make IMG=/path/to/ubuntu-26.04-preinstalled-server-riscv64.img all

Makefile 默认从
``workdir/scratch/gadget/install/u-boot-spacemit/u-boot.itb``
读取 U-Boot FIT（本地 ``make image`` 完成后自动生成）。
烧写下载镜像时可：

* 保留上次构建的 ``workdir/``，或
* 直接调用 ``image_flash.py`` 并手动提供 ``temp/u-boot.itb``（见下文）。

手动执行各步骤：

.. code-block:: bash

    # 1. 从镜像中提取各分区文件至 ./temp
    python3 image_flash.py \
        --img path/to/ubuntu-26.04-preinstalled-server-riscv64.img \
        --partition partition_universal.json

    # 2. 将 u-boot.itb 放入 ./temp
    #    （fastboot BootROM 暂存步骤需要此文件；不会写入运行时 flash 分区）
    cp /path/to/u-boot.itb temp/u-boot.itb

    # 3. 执行烧写
    sudo python3 image_flash.py --fastboot fastboot.yaml

选择性烧写
~~~~~~~~~~

开发调试时可用 ``--only`` 和 ``--skip`` 过滤要操作的分区
（二者互斥，支持逗号分隔多个名称）：

.. code-block:: bash

    # 只重刷 EFI 系统分区
    sudo python3 image_flash.py --fastboot fastboot.yaml --only esp

    # 重刷除根文件系统外的所有分区（迭代更快）
    sudo python3 image_flash.py --fastboot fastboot.yaml --skip writable

    # 提取阶段同样支持上述参数
    python3 image_flash.py --img <img> --partition partition_universal.json --only esp

当 ``--only`` 指定的分区不存在于某个分区表时，对应的 fastboot 阶段会自动跳过
（例如 ``--only esp`` 会完全跳过 MTD/NOR 阶段，直接进入 GPT 上下文）。

首次启动
--------

默认账户：``ubuntu`` / ``ubuntu``。

镜像内置 ``ubuntu-desktop`` 及 PowerVR GPU 用户空间驱动；
首次启动时会自动执行 ``apt-get full-upgrade`` 并恢复 systemd-resolved 符号链接。

仓库结构
--------

::

    image-definition.yaml       ubuntu-image classic 构建定义
    gadget.in/                  gadget snap 源（分区布局 + 固件）
        Makefile                从 spacemit/k3 PPA 拉取固件 (.deb)
        gadget.yaml             GPT 布局
        edk2.itb                EDK2 UEFI FIT（内嵌二进制）
        grub.cfg                ESP grub 引导桩
        user-data / meta-data   cloud-init NoCloud 配置
    grub.cfg                    rootfs /boot/grub/grub.cfg（UEFI 菜单）
    grub.d/                     /etc/default/grub.d 片段
    setup-scripts.sh            镜像内定制脚本（apt 升级、恢复 resolv.conf）
    spacemit-ppa-preference     spacemit/k3 PPA 的 APT 优先级固定
    Makefile                    镜像构建 + 烧写工作流入口
    image_flash.py              分区提取与 fastboot 驱动
    fastboot.yaml               fastboot 烧写流程
    partition_universal.json    GPT 分区表（块设备）
    partition_4M.json           MTD/NOR 分区表（启动 SPI Flash）
