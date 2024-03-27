---
categories:
- SSD
date: 2023-08-16 20:22:00 +0800
last_modified_at: 2024-03-27 16:15:10 +0800
tags:
- linux
- io_uring
- nvme
title: 使用 io_uring 进行 NVMe 命令的异步透传
---

> 2024/03/27 更新：USENIX FAST'24 上的论文 [I/O Passthru: Upstreaming a flexible and efficient I/O Path in Linux](https://www.usenix.org/conference/fast24/presentation/joshi) 详细介绍了 NVMe 驱动的 passthru。
{: .prompt-info }

Linux 5.19 开始加入了 `IORING_OP_URING_CMD` 的支持，该 io_uring 命令可以理解为异步的 ioctl，可以将对应的子命令交给对应的驱动异步执行。其中 NVMe 驱动加入了 `NVME_URING_CMD_IO` 这一子命令，该命令和原来 NVMe 驱动中的 `NVME_IOCTL_IO_CMD` ioctl 命令类似，能够支持 NVMe 命令的透传（passthrough），使用户直接提交 NVMe 命令对应的 SQE，并获取对应的 CQE（一般情况下程序是通过内核的 bio、vfs 等层次间接的与 SSD 通信）。

NVMe 命令集目前分成了 NVM、KV、Zone 三种，并且每种都可以有 vendor-specific 的命令，这些命令对应的就是非标准的 SQE。用户想要使用厂商特定的命令或者开发者想要扩展 NVMe 命令集就可以使用透传的方式，从而避免修改 NVMe 驱动。

在 Linux 5.19 之前，使用内核 nvme 驱动的情况下只能够通过 ioctl 进行透传，然而 ioctl 是同步执行的，若需要大量并发地向 SSD 发送命令就会遇到困难。Linux 5.19 之后就加入了 `IORING_OP_URING_CMD` 和 `NVME_URING_CMD_IO`，使得可以批量、异步地透传 NVMe 命令。

io_uring 本身是 Linux 内核提出的一种新的异步 IO 接口，其使用方式与 NVMe 类似，在内存中有一个共享队列对（queue pair），用户态程序将 IO 操作比如文件的 read/write、网络的 send/recv 这些请求写入到共享队列中，之后内核有专门的线程从队列中获取对应的命令并执行 IO，执行结束后将结果写入到完成队列，用户态程序最后再从完成队列中获取结果。通过这样的方式就可以避免用户程序同步地等待 IO 的执行，在提交了任务后用户程序就可以做其他工作，之后再从完成队列中获取结果。

## 代码

一个简单的代码样例如下所示，需要内核版本大于等于 5.19，并需要安装 `liburing`。Github gist: [io\_uring nvme passthru](https://gist.github.com/cs-qyzhang/27c6e0821670fe02ddaede1046135eba)。

```c
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <linux/nvme_ioctl.h>
#include <liburing.h>

int iouring_setup(unsigned entries, struct io_uring *ring)
{
    return io_uring_queue_init(entries, ring, IORING_SETUP_SQE128 |
                                              IORING_SETUP_CQE32);
}

void iouring_exit(struct io_uring *ring)
{
    io_uring_queue_exit(ring);
}

int iouring_passthru_enqueue(struct io_uring *ring, int fd,
                             const struct nvme_uring_cmd *cmd)
{
    // https://github.com/joshkan/fio/blob/big-cqe-pt.v4/engines/io_uring.c
    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    if (!sqe) {
        printf("Failed to get io_uring sqe\n");
        return -1;
    }
    // fd = open('/dev/ng0n1')
    // see https://lpc.events/event/11/contributions/989/attachments/747/1723/lpc-2021-building-a-fast-passthru.pdf
    sqe->fd = fd;
    sqe->opcode = IORING_OP_URING_CMD;
    sqe->cmd_op = NVME_URING_CMD_IO;  // see linux/nvme_ioctl.h
    memcpy(sqe->cmd, cmd, sizeof(struct nvme_uring_cmd));
    return 0;
}

int iouring_submit(struct io_uring *ring)
{
    int nr = io_uring_submit(ring);
    if (nr < 0) {
        perror("io_uring_submit");
        return -1;
    }
    return nr;
}

int iouring_wait_nr(struct io_uring *ring, int nr)
{
    struct io_uring_cqe *cqes = NULL;
    if (io_uring_wait_cqe_nr(ring, &cqes, nr) < 0) {
        perror("io_uring_wait_cqes");
        return -1;
    }
    for (int i = 0; i < nr; i++) {
        struct io_uring_cqe *cqe = &cqes[i];
        int err = cqe->big_cqe[0] || cqe->res;
        if (err) {
            fprintf(stderr, "io_uring_wait_cqe_nr: %d, %s\n", err, strerror(-err));
            return -1;
        }
    }
    return nr;
}
```

## 参考文献

[1] Linux-nvme mailing list: [Fixed-buffers io\_uring passthrough over nvme-char - Kanchan Joshi](https://lore.kernel.org/linux-nvme/20210805125539.66958-1-joshi.k@samsung.com/) \
[2] io_uring fio: [GitHub - joshkan/fio at uring\_cmd\_nvme\_v4](https://github.com/joshkan/fio/blob/big-cqe-pt.v4/engines/io_uring.c)\
[3] liburing: [GitHub - axboe/liburing](https://github.com/axboe/liburing)\
[4] io_uring doc: [Lord of the io\_uring documentation](https://unixism.net/loti/index.html)\
[5] Presentation: [Building a fast NVMe passthru](https://lpc.events/event/11/contributions/989/attachments/747/1723/lpc-2021-building-a-fast-passthru.pdf)\
[6] LWN: [ioctl() for io\_uring]( https://lwn.net/Articles/844875/ )\
[7] Presentation: [What's new with io\_uring](https://kernel.dk/axboe-kr2022.pdf)\
[8] Manpage: [io\_uring(7) - Linux manual page](https://man7.org/linux/man-pages/man7/io_uring.7.html)\
[9] Manpage: [io\_uring\_setup(2) - Linux manual page](https://man7.org/linux/man-pages/man2/io_uring_setup.2.html)