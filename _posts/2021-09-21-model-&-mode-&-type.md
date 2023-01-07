---
categories:
- Storage
- Persistent Memory
date: 2021-09-21 17:00:00 +0800
last_modified_at: 2023-01-07 17:51:18 +0800
tags:
- optane
- memory
title: Model/Mode/Type of Intel Optane Persistent Memory
---

## Overview

| Name                    | Description                                   | Content                                                         |
| ----------------------- | --------------------------------------------- | --------------------------------------------------------------- |
| Operating Mode          | This is the mode associated with Intel DC PMM | 1. Memory Mode (MM, 2LM)<br>2. App Direct (AD, 1LM)                |
| Programming Model       | SNIA NVM Programming Model                    | 1. NVM.BLOCK<br>2. NVM.FILE<br>3. NVM.PM.VOLUME<br>4. NVM.PM.FILE        |
| Type                    | Type defined by LIBNVDIMM driver              | 1. PMEM<br>2. BLK (deprecated)                                     |
| Mode (under App Direct) | Mode of pmem namespace                        | 1. fsdax<br>2. devdax<br>   2.1 system-ram (daxctl)<br>3. sector<br>4. raw     |
| Normal RAM              | Using PMEM as normal RAM, coexist with DRAM   | Kind of sub-mode of devdax, called system-ram in utility daxctl |

## Operating Mode

In memory mode, NVDIMMs are used as main memory, DRAM is treated as a write-back, direct-mapped cache (because of that memory mode is referred as 2LM, 2-level memory). Hardware ensures that data is not available after shutdown (data will erased).

## SNIA NVM Programming Model

| Name          | Model                                      |
| ------------- | ------------------------------------------ |
| NVM.BLOCK     | Treat NVM as a block device                |
| NVM.FILE      | Build file system upon NVM.FILE            |
| NVM.PM.VOLUME | Like 1, but treat NVM as Persistent Memory |
| NVM.PM.FILE   | Build file system upon NVM.PM.VOLUME       |

==TODO==

## LIBNVDIMM Type

BLK is deprecated. See [SUSE Administration Guide](https://documentation.suse.com/sles/15-SP1/html/SLES-all/cha-nvdimm.html).

==TODO==

## Namespace Mode

PMEM is divided into regions, inside region space can be further divided into namespace. PMEM namespace is similar to NVMe namespace, every namespace will be shown as a device under `/dev`.

Since different namespaces present as different devices, so different namespaces can have different device drivers. This leads to namespace mode.

Namespace can be configured using `ndctl` utility.

There are four different modes:

1. **fsdax**. This is the default mode of `ndctl`, If a namespace is configured as fsdax, the corresponding device is a block device, just like a normal block device, it can be parted, building file system above partition. This mode will bypass page cache, if building pmem-aware file system with DAX support, this mode can leverage the persistent memory benefits.
2. **devdax**. Like fsdax, this mode will have DAX feature: bypassing page cache. Unlike fsdax, device is a character device, and cannot build file system above device. Device must used as a whole, this mode can be used in RDMA environment.
3. **sector**. Like fsdax, device is a block device but without DAX support. This mode will use BTT (Block Translation Table) driver, this driver enable atomic block feature like SSD, it can ensure that a in-flight data block is written as a whole or not written at all. This is implemented using a block translation table. With this mode, application targets normal SSD/HDD can running upon PMEM without code change.
4. **raw**. ==TODO==.

All modes support partition except devdax.

> Be carefully! if `ndctl list` reports a device is in devdax mode, it may actually in `system-ram` mode which is a kind of subcategory of devdax (see "Normal RAM" section below), use `daxctl list` command to see the real mode of a devdax device.
{: .prompt-warning }

## Normal RAM

Under app direct mode, linux kernel can be configured to use Optane DC as DRAM, kernel considers Optane DC to be slower memory and DRAM to be faster memory, and puts them in two separate NUMA nodes. #numa

This mode is supported by `kmem` kernel module, a part of DAX module. This module is introduced since linux 5.1. To use `dax_kmem` driver, pmem needs to be configured in _App Direct_ mode, and configure corresponding namespace to `devdax`, then using `daxctl` utility to configure this namespace to `system-ram` mode:

```bash
$ daxctl migrate-device-model
$ udevadm trigger # or reboot
$ daxctl reconfigure-device dax0.0 --mode=system-ram
$ reboot
```

## References

1. [Persistent Memory | Administration Guide | SUSE Linux Enterprise Server 15 SP1](https://documentation.suse.com/sles/15-SP1/html/SLES-all/cha-nvdimm.html)
2. [pmem.io: Memkind Support for KMEM DAX Option](https://pmem.io/2020/01/20/memkind-dax-kmem.html)
3. [Linux Kernel 中 AEP 的现状和发展](https://kernel.taobao.org/2019/05/NVDIMM-in-Linux-Kernel/)
4. [[0/5,v5] Allow persistent memory to be used like normal RAM - Patchwork](https://patchwork.kernel.org/project/linux-nvdimm/cover/20190225185727.BCBD768C@viggo.jf.intel.com/)
5. [Opportunities for Partitioning Non-volatile Memory DIMMs Between Co-scheduled Jobs on HPC Nodes](zotero://select/items/@goglinOpportunitiesPartitioningNonvolatile2020)