---
categories:
- DevOps
- Block
date: 2023-02-10 18:55:01 +0800
tags:
- linux
- devops
- rdma
- ceph
title: Ceph 块存储 RBD 在 RDMA 网络下的部署
---

这里记录一下 Ceph 的块存储 RBD 使用 RDMA 网络（RoCE v2）的配置过程。主要参考的是 Ceph 的官方文档（然而并没有 RDMA 配置部分）以及 [Bring Up Ceph RDMA](https://enterprise-support.nvidia.com/s/article/bring-up-ceph-rdma---developer-s-guide)。

## 集群配置

刚开始尝试使用 `cephadm bootstrap` 命令配置，但可能是因为 RDMA 网卡没有暴露给 docker 容器的原因，这种方式没有配置成功。于是选择了手动配置。

手动编译 Ceph 出了各种问题，于是选择了直接使用官方提供的 <https://download.ceph.com/> apt 源，Ubuntu 20.04 默认的 Ceph 版本似乎不行。见 [Get Packages — Apt](https://docs.ceph.com/en/latest/install/get-packages/#apt)。

为了方便这里把认证都关闭了，所以下面没有运行生成 keyring 的过程。

首先是 monitor map 的创建，见 [Manual Deployment](https://docs.ceph.com/en/latest/install/manual-deployment/)：

```bash
monmaptool --create --add {hostname} {ip-address} --fsid {uuid} /tmp/monmap
sudo -u ceph mkdir /var/lib/ceph/mon/ceph-{hostname}
sudo -u ceph ceph-mon --mkfs -i {hostname} --monmap /tmp/monmap
```

之后需要修改 `/etc/ceph/ceph.conf` 配置文件。建议先在其他地方写配置文件然后拷贝过去，在后续出错删除集群时会把 `/etc/ceph/ceph.conf` 删掉。对应的配置文件如下所示，使用 `show_gids` 可以获取 RDMA 网卡对应的 gid。

```
[global]
fsid = <uuidgen>
mon host = <ethernet ip addr, not roce port addr>
mon initial members = <hostname>
public network = <ethernet subnet, e.g. 192.168.0.0/16>
auth cluster required = none
auth service required = none
auth client required = none
osd pool default size = 1
ms type = async+rdma
ms cluster type = async+rdma
ms async rdma polling us = 0
ms async rdma device name = mlx5_0
ms async rdma local gid = 0000:0000:0000:0000:0000:xxxx:xxxx:xxxx
```

然后是需要改 memlock 的限制（RDMA 需要）。先在 `/etc/security/limits.conf` 文件中加入以下内容：

```
* soft memlock unlimited
* hard memlock unlimited
root soft memlock unlimited
root hard memlock unlimited
ceph soft memlock unlimited
ceph hard memlock unlimited
```

之后重新登录生效。然后在 `/lib/systemd/system` 文件夹下的 `ceph-mon@.service`，`ceph-mgr@.service`，`ceph-osd@.service` 文件中加入以下内容（注意原来的文件有没有这些配置，如果有的话先删掉）。见 [Bring Up Ceph RDMA](https://enterprise-support.nvidia.com/s/article/bring-up-ceph-rdma---developer-s-guide)。

```systemd
[Service]
LimitMEMLOCK=infinity
PrivateDevices=no
```

之后运行如下命令启动 monitor 和 manager。如果启动出错可以使用 `sudo cephadm logs --fsid <fsid> --name mon.{hostname}` 来查看 monitor 的日志（mgr 的 name 是 `mgr.{hostname}`）。

```bash
sudo systemctl daemon-reload
sudo systemctl start ceph-mon@{hostname}
sudo systemctl start ceph-mgr@{hostname}
```

如果出错了可以运行以下命令删除集群重新开始（不再需要进行 monitor map 的创建）：

```bash
sudo cephadm rm-cluster --fsid <fsid> --force
sudo systemctl stop ceph-mon@{hostname}
sudo systemctl stop ceph-mgr@{hostname}
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

如果没有问题那么运行 `ceph -s` 会显示该集群信息。在配置时每次运行 `ceph` 等命令都会出现一次 `Infiniband send_cm_meta send returned error 111: (111) Connection refused` 和 `Infiniband to_dead failed to send a beacon: (111) Connection refused` 错误，但似乎没有影响。

之后就可以添加 OSD（bluestore），见 [Adding OSDs](https://docs.ceph.com/en/latest/install/manual-deployment/#adding-osds) ：

```shell
sudo ceph-volume lvm create --data /dev/nvmeXnX
sudo ceph-volume lvm list
sudo ceph-volume lvm activate {OSD ID} {OSD FSID}
```

然后还需要创建 pool 和 image，见 [Basic Block Device Commands](https://docs.ceph.com/en/latest/rbd/rados-rbd-cmds/) ：

```bash
rbd pool init <pool-name>
rbd create --size {megabytes} --object-size {objectsize} {pool-name}/{image-name}
```

没有问题的话集群就部署完成了。

### 客户端配置

客户端上需要有集群的 `/etc/ceph/ceph.conf` 配置文件。将服务器上的配置文件复制到客户端的 `/etc/ceph` 下即可。见 [Chapter 4. Client Installation](https://access.redhat.com/documentation/en-us/red_hat_ceph_storage/2/html/installation_guide_for_ubuntu/client_installation#ceph_command_line_interface_installation)。在客户端上运行 `ceph -s` 查看是否成功。

### fio 测试

[fio](https://github.com/axboe/fio.git) 中包含 rbd 的 ioengine，源码的 `examples/rbd.fio` 配置文件就是用于对 Ceph 的 rbd 进行测试。

为了编译 fio，让 fio 识别到 rbd 和 rados，首先安装 `librbd-dev` 和 `librados-dev` 两个库。之后按照 fio 的编译步骤运行即可。

### tcpdump

Ubuntu 20.04 中默认的 tcpdump 和 libpcap 无法监控 `mlx5_0` 设备，需要自行编译 libpcap 和 tcpdump。Git clone 的 tcpdump 和 libpcap 两个目录应该在同一级，tcpdump 会在它文件夹的 `../libpcap` 中寻找 libpcap。按照对应的编译步骤先编译 libpcap 再编译 tcpdump。使用以下命令可以监控 `mlx5_0` 的流量。

```bash
sudo tcpdump -i mlx5_0
```