SpacemiT K3 gadget
==================

为 SpacemiT K3 Pico-ITX 开发板构建支持 UEFI 启动的 Ubuntu RISC-V 预装镜像，
并通过 fastboot 完成烧写。

`English <README.rst>`_

预构建镜像
----------

如果只需要烧写开发板，从项目 GitHub Releases 获取最新的
``ubuntu-26.04-preinstalled-desktop-riscv64.img.zst`` （及其校验文件），
然后直接跳至 `烧写开发板`_ 章节。

烧写开发板
----------

硬件准备：将 SpacemiT K3 Pico-ITX 开发板切换至刷机模式。

在 Ubuntu （22.04 及之后版本）主机上安装依赖：

.. code-block:: bash

    sudo apt-get update
    sudo apt-get install git ubuntu-dev-tools fastboot
    git clone https://github.com/spacemit-com/K3-Ubuntu-Images.git gadget
    cd gadget

一键完成刷机：

.. code-block:: bash

    make IMG=/path/to/ubuntu-26.04-preinstalled-desktop-riscv64.img.zst all

手动执行各步骤：

.. code-block:: bash

    # 1. 从镜像中提取各分区文件至 ./temp
    python3 image_flash.py \
        --img path/to/ubuntu-26.04-preinstalled-desktop-riscv64.img \
        --partition partition_universal.json

    # 2. 将 u-boot.itb(从ppa获取的) 放入 ./temp
    #    BootROM 会通过 USB 将其加载至内存（RAM）中运行；它在 RAM 中充当临时
    #    fastboot 服务端，不会被写入任何存储分区。
    cp /path/to/u-boot.itb temp/u-boot.itb

    # 3. 执行烧写
    sudo python3 image_flash.py --fastboot fastboot.yaml

首次启动
--------

默认账户：``ubuntu`` / ``ubuntu``。

镜像内置 ``ubuntu-desktop`` 及 Chromium 浏览器。

构建镜像
--------

在 Ubuntu 26.04 主机上安装构建依赖：

.. code-block:: bash

    sudo apt-get update
    sudo apt-get install git snapd qemu-user-static ubuntu-dev-tools \
                         python3-yaml fastboot
    sudo snap install --classic ubuntu-image

克隆并构建：

.. code-block:: bash

    git clone https://github.com/spacemit-com/K3-Ubuntu-Images.git gadget
    cd gadget
    make image          # 通过 ubuntu-image 进行全量构建

可用构建变体：

.. code-block:: bash

    make image-debug    # 带 --debug 的全量构建

构建产物路径::

    workdir/ubuntu-26.04-preinstalled-desktop-riscv64.img

运行时启动链
------------

::

                                ┌→ ESOS（功耗管理核 + 实时任务管理核，独立运行）
    BootROM → FSBL（U-Boot SPL） ┤
                                └→ OpenSBI → EDK2 UEFI → GRUB → Linux

各阶段说明：

- **BootROM** 读取 ``bootinfo`` 分区以定位并校验 FSBL，然后将控制权转交给它。
- **FSBL** （``fsbl`` 分区，U-Boot SPL）完成时钟、DRAM 及外设初始化，
  随后串行启动如下负载：

  - **ESOS** （``esos`` 分区）——Energy Service OS，包含两个独立运行的
    RTOS 子系统，均运行在独立管理核心上，与应用核心的启动流程相互独立：

    - **功耗管理核**——一款面向功耗管理设计的 RTOS 多任务实时操作系统。
    - **运行时实时任务管理核**——一款面向实时任务处理的 RTOS 多任务实时操作系统。
  - **OpenSBI** （``opensbi`` 分区）——在应用核心上建立 SBI 运行时环境，
    并启动下一阶段负载——EDK2。
- **EDK2 UEFI** （``uboot`` 分区，存储 ``edk2.itb``）提供完整的 UEFI 运行环境。
  该分区名称沿用自 U-Boot 启动的分区布局，但运行时负载实际上是 EDK2 固件，而非 U-Boot。
- **GRUB** 由 EDK2 从 ESP 加载（``EFI/boot/bootriscv64.efi``）。
  ESP 上的桩 ``grub.cfg`` 将 GRUB 重定向至 ``writable`` 分区上的
  ``/boot/grub/grub.cfg``。
- **Linux** 由 GRUB 按照 ``/boot/grub/grub.cfg`` 中的参数启动。

u-boot.itb 的作用
-----------------

``u-boot.itb`` **不参与**运行时启动链，仅在烧写阶段作为临时 fastboot 服务使用：

1. SpacemiT K3 BootROM 处于 USB 下载模式时，可通过 USB 接收一个 FIT 镜像并将其
   完整加载到内存（RAM）中。
2. 主机将 ``u-boot.itb``（包含 fastboot 服务端的完整 U-Boot 构建产物）上传到
   开发板的 RAM 中。
3. U-Boot 在 RAM 中运行，向主机暴露 fastboot 协议。
4. 主机随后通过 ``fastboot`` 将所有 GPT/NOR 分区镜像写入目标存储介质。
5. 下次上电时，开发板从新写入的分区按上述运行时启动链正常启动；
   ``u-boot.itb`` 从不持久化到任何存储分区。

GRUB 初始化
------------

镜像采用两阶段 GRUB 初始化方案。

**预置阶段（镜像构建时）：**

- ESP 中预置了编译好的 ``grubriscv64.efi`` 和一个最小桩 ``grub.cfg``
  （``gadget.in/grub.cfg``），该桩配置仅将 GRUB 重定向至 ``writable``
  分区的 ``/boot/grub/grub.cfg``。
- ``writable`` 根文件系统中预置了一份生成好的 ``/boot/grub/grub.cfg``
  （来自本仓库根目录的 ``grub.cfg``），可满足首次上电时的正常启动需求。

**首次启动（运行时）：**

系统首次启动时，cloud-init 任务会自动执行：

- ``grub-install`` — 为当前运行系统安装 GRUB EFI 二进制文件，并在 UEFI NVRAM
  中注册启动项，替换预置的通用桩文件。
- ``update-grub`` — 根据已安装的内核、``/etc/grub.d/`` 模板及
  ``/etc/default/grub`` 设置，重新生成 ``/boot/grub/grub.cfg``，
  替换镜像构建时预置的文件。

此后每次内核升级都会自动触发 ``update-grub``，保持启动菜单与系统同步。

仓库结构
--------

::

    image-definition.yaml       ubuntu-image classic 构建定义
    gadget.in/                  gadget 源（分区布局 + 固件）
        Makefile                从 spacemit/k3 PPA 拉取固件 (.deb)
        gadget.yaml             GPT 布局
        edk2.itb                EDK2 UEFI FIT（内嵌二进制）
        grub.cfg                ESP grub 引导桩
        user-data / meta-data   cloud-init NoCloud 配置
    grub.cfg                    rootfs /boot/grub/grub.cfg（UEFI 菜单）
    grub.d/                     /etc/default/grub.d 片段
    setup-scripts.sh            镜像内定制脚本（apt 升级）
    spacemit-ppa-preference     spacemit/k3 PPA 的 APT 优先级固定
    Makefile                    镜像构建 + 烧写工作流入口
    image_flash.py              分区提取与 fastboot 驱动
    fastboot.yaml               fastboot 烧写流程
    partition_universal.json    UFS/SSD的GPT分区表
    partition_4M.json           NOR的分区表
