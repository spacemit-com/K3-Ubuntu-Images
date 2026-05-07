#!/bin/bash -ex
rm -f /etc/resolv.conf
cat >/etc/resolv.conf <<EOF
nameserver 10.0.26.11
nameserver 114.114.114.114
EOF

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get full-upgrade -y --allow-downgrades

rm /etc/resolv.conf
ln -s /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf