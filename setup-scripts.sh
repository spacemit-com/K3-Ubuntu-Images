#!/bin/bash -ex
rm -f /etc/resolv.conf
cat >/etc/resolv.conf <<EOF
nameserver 10.0.26.11
nameserver 114.114.114.114
EOF

apt-get update -o Acquire::http::Timeout=60 -o Acquire::https::Timeout=60 -o Acquire::Retries=5
DEBIAN_FRONTEND=noninteractive apt-get full-upgrade -y --allow-downgrades -o Acquire::http::Timeout=60 -o Acquire::https::Timeout=60 -o Acquire::Retries=5

# k3-preview 在 image-definition.yaml 设 keep-enabled:true,撑过上面的
# full-upgrade(防 BSP 包被 --allow-downgrades 降级回 k3/base 旧版)。
# upgrade 完成后在此删除,使其不进入最终镜像(用户不受影响)。
rm -f /etc/apt/sources.list.d/*k3-preview*.sources
apt-get clean

rm /etc/resolv.conf
ln -s /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf