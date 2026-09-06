#!/bin/sh
# Read-only discovery. Never prints environment files, private keys or full nginx configs.
set -u
role=${1:-node}
printf '%s\n' '=== host ==='
date -u
uname -srm
id
printf '%s\n' '=== runtimes ==='
command -v python3 >/dev/null 2>&1 && python3 --version
command -v nginx >/dev/null 2>&1 && nginx -v 2>&1
command -v tailscale >/dev/null 2>&1 && tailscale version | head -n 1
printf '%s\n' '=== listeners ==='
command -v ss >/dev/null 2>&1 && ss -lnt
printf '%s\n' '=== tailscale addresses ==='
command -v tailscale >/dev/null 2>&1 && tailscale ip -4
printf '%s\n' '=== storage and permissions ==='
if [ "$role" = node ]; then
    ls -ld /data /data/lx 2>/dev/null || true
    df -hT /data/lx 2>/dev/null || true
    command -v findmnt >/dev/null 2>&1 && findmnt -T /data/lx -o SOURCE,FSTYPE,TARGET
    command -v getfacl >/dev/null 2>&1 && getfacl -p /data/lx 2>/dev/null || true
fi
printf '%s\n' '=== SELinux ==='
command -v getenforce >/dev/null 2>&1 && getenforce || true
printf '%s\n' '=== service state ==='
if command -v systemctl >/dev/null 2>&1; then
    systemctl is-active tailscaled.service 2>/dev/null || true
    if [ "$role" = edge ]; then
        systemctl is-active nginx.service 2>/dev/null || true
        systemctl is-enabled certbot.timer 2>/dev/null || true
    fi
fi
printf '%s\n' 'Read-only preflight complete. Review ACLs, quotas, grants and certificate renewal separately.'