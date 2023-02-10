---
categories:
- DevOps
date: 2023-01-04 15:54:38 +0800
last_modified_at: 2023-01-06 17:32:04 +0800
tags:
- linux
- devops
title: Linux 硬盘恢复
---

2023 年 1 月 4 日记录一下硬盘分区表损坏以及文件系统损坏的恢复过程（虽然没有成功恢复 ）。

起因是因为某同学切换内核不知道是怎么操作的导致服务器不能连接。去机房发现对应的机器卡在了启动界面，进入 BIOS 发现无法识别到 NVMe SSD 盘。引导进入 U 盘的 Ubuntu Server Live，在 Help 中进入终端，发现系统能够识别到 NVMe SSD 盘 /dev/nvme0n1，通过 `fdisk -l` 发现没有分区表。搜索后发现可以通过 `testdisk` 来恢复分区表。Ubuntu Server Live 本身没有 `testdisk`，需要通过 `apt` 安装。先退出终端，将安装过程中的配置网络那一步运行完，之后再次进入终端安装 `testdisk`。运行 `testdisk` 尝试分析硬盘的分区表。`testdisk` 发现了两个分区，如下图所示的两个 `Linux filesys. data` 分区。

![testdisk 查找分区表](https://qyzhang-obsidian.oss-cn-hangzhou.aliyuncs.com/IMG_20230104_105800.jpg)

在 `testdisk` 完成了分区表的搜索后可以在对应分区上按 P 来查看对应分区的文件。刚开始没有发现这个功能，运行的是如下操作。

尝试挂载这两个分区看看这两个分区是否是正确的，以及分区对应的文件系统是否正常。首先尝试直接 mount，运行如下命令：

```bash
mkdir /mnt/a
mount -t auto -o offset=$((1050624*512)) /dev/nvme0n1 /mnt/a
```

但不能挂载，忘记了报的是什么错。但后来发现如果 mount 报的错误是 `wrong fs type, bad option, bad superblock` 等好像意味着 offset 是错误的，也就是 offset 对应的并不是一个分区，而如果报的是 `structure needs cleaning` 错误那么说明对应的 offset 是一个分区而且对应的文件系统有损坏，这时可以使用 `fsck` 来解决文件系统的问题。

在确定了这两个分区的 offset 是正确的之后，就需要用 `fsck` 来修复文件系统。但是 `fsck` 不能够像 `mount` 那样指定 offset，为了能够执行 `fsck` 有两种方式，第一种是先通过 `testdisk` 把分区表恢复，第二种是通过 `losetup` 将对应的分区设置成一个 `/dev/loop` 设备。执行以下命令：

```bash
losetup -o $((1050624*512)) /dev/loopXX /dev/nvme0n1
fsck /dev/loopXX
```

运行 `fsck` 之后按 a 会对所有的进行确认（注意！这样 `fsck` 会对分区数据进行修改，在确保分区信息正确且没有其他方法恢复时才使用该方法）。恢复之后就可以 mount 该 loop 设备，进入后发现只有 `lost+found` 文件夹，里面有一些 `fsck` 恢复的文件，但是由于 inode 信息缺失不知道他们的路径，通过 `file *` 可以列出来这些文件的类型，随便打开一个文本文件能够发现文件内容是正常的，但由于文件比较多已经难以恢复原状。这就代表着恢复失败，只能够重装系统。

![fsck 将文件恢复到了 lost+found 中](https://qyzhang-obsidian.oss-cn-hangzhou.aliyuncs.com/IMG_20230104_115052.jpg)

运行以下命令取消之前的 `losetup` 操作。

```bash
losetup -d /dev/loopXX
```

之后就安装 Ubuntu Server。安装后发现还是启动不了，BIOS 仍然无法识别到 NVMe SSD 盘。经过一番折腾发现好像将 BIOS PCIe 下的一个 NVMe 固件源选项从 Device Vender Defined Support 更换为 AMI Native Support 后重启就可以识别到了（首先将所有 BIOS 的选项恢复成默认的之后再运行的这步操作）。不清楚是否是这个选项的问题，在恢复了 BIOS 选项之后还执行了又一次重装系统的操作，但重装后仍然不行，改了这个选项重启才能够正常启动。

![BIOS 的 NVMe 固件选项](https://qyzhang-obsidian.oss-cn-hangzhou.aliyuncs.com/IMG_20230104_141742.jpg)