---
title: "BSides 2026 BOF CTF - Deployment Script"
type: technique
tags: [ctf, bof, deploy, docker, infra]
phase: exploitation
date_created: 2026-05-22
date_updated: 2026-06-01
sources: [ctf-bsides-buffer-2026-deploy]
---

# BSides 2026 BOF CTF - Deployment

Single script deploys full 4-flag chain on any Ubuntu host with Docker.

---

## Prerequisites

- Ubuntu host (20.04 / 22.04 / 24.04)
- Internet access (pulls `ubuntu:20.04` and `alpine`)
- Script self-elevates to root via sudo
- User: `ubuntu:bsidesTom123as`, `root:bsides2026Tom123as` (locked, SSH key only)
- root - only ssh-key based
- Hosting `https://evps.net/`

---

## Quick Start

```bash
sudo bash deploy.sh              # fresh deploy, auto-generates flags
sudo bash deploy.sh --redeploy   # tear down + rebuild with new flags
sudo bash deploy.sh --dirtyfrag  # also build dirtyfrag kernel LPE on host
sudo bash deploy.sh --clean      # remove everything
```

---

## After Deployment

```bash
# Export binary for participants (RUNTIME_DIR deleted post-deploy — use docker ps directly)
CID=$(sudo docker ps --filter name=bof-ctf -q)
sudo docker cp ${CID}:/opt/adminpanel ./adminpanel
# distribute ./adminpanel + host IP to participants

# Validate full 4-flag chain
sudo bash testing.sh
```

---

## deploy.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

# BSides 2026 BOF CTF — one-file deployment
# Flags: bof.txt -> docker.txt -> user.txt -> root_flag (binary, cgroup-gated)
#
# Usage:
#   sudo bash deploy.sh [--redeploy] [--dirtyfrag] [--clean]

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

REDEPLOY=false
DIRTYFRAG=false
CLEAN=false

for arg in "$@"; do
  case "${arg}" in
    --redeploy)  REDEPLOY=true  ;;
    --dirtyfrag) DIRTYFRAG=true ;;
    --clean)     CLEAN=true     ;;
    -h|--help)   echo "Usage: $0 [--redeploy] [--dirtyfrag] [--clean]"; exit 0 ;;
    *)           echo "[!] Unknown argument: ${arg}"; exit 1 ;;
  esac
done

RUNTIME_DIR="/root/.ctf-runtime"
mkdir -p "${RUNTIME_DIR}"
chmod 700 "${RUNTIME_DIR}"

write_runtime_files() {

cat > "${RUNTIME_DIR}/src.c" <<'EOF'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static const char *s1 = "auth_token_validator_v2";
static const char *s2 = "security_module_initialized";
static const char *s3 = "validate_session_integrity";
static const char *s4 = "admin_bypass_protection_enabled";

static void sanitize(unsigned char *buf, int len) {
    if (len <= 0) return;
    for (int i = 0; i < len; i++) {
        if (buf[i] == 0x0a || buf[i] == 0x0d || buf[i] == 0x20 || buf[i] == 0x0b)
            buf[i] = 0x00;
    }
}

static void __attribute__((used, noinline)) gadget_stub(void) {
    __asm__ volatile(
        "nop\n\t" "nop\n\t" "nop\n\t"
        "jmp *%%rsp\n\t"
        "nop\n\t"
        "jmp *%%rsp\n\t"
        ::: "memory");
}

static void auth_key_check(void) {
    char buf[64];
    write(1, "Authentication key: ", 20);
    sanitize((unsigned char *)buf, (int)read(0, buf, 256));
    write(1, "Access denied\r\n", 15);
}

int main(void) {
    if (s4[0] == '\0') return 1;
    write(1, "=== Auth Gateway v1.3 ===\r\n", 27);
    write(1, "Session module: ", 16);
    write(1, s2, strlen(s2));
    write(1, "\r\n", 2);
    write(1, "Validation routine: ", 20);
    write(1, s3, strlen(s3));
    write(1, "\r\n", 2);
    auth_key_check();
    return 0;
}
EOF

cat > "${RUNTIME_DIR}/start.sh" <<'EOF'
#!/bin/bash
set -euo pipefail
iptables -F INPUT 2>/dev/null || true
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -p tcp --dport 8443 -j ACCEPT
echo "[*] firewall up: TCP/8443 open"

if [[ -S /var/run/docker.sock ]]; then
  SOCK_GID="$(stat -c '%g' /var/run/docker.sock)"
  SOCK_GROUP="$(getent group "${SOCK_GID}" | cut -d: -f1 || true)"
  if [[ -z "${SOCK_GROUP}" ]]; then
    groupadd -g "${SOCK_GID}" dockersock || true
    SOCK_GROUP="dockersock"
  fi
  usermod -aG "${SOCK_GROUP}" ctf || true
fi

chattr +i /home/ctf/bof.txt /root/docker.txt 2>/dev/null || true

rm -f /start.sh
exec su ctf -s /bin/bash -c 'socat TCP-LISTEN:8443,reuseaddr,fork EXEC:/opt/adminpanel'
EOF

cat > "${RUNTIME_DIR}/Dockerfile" <<'EOF'
FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libc6-dev libcap2-bin make socat iptables iproute2 python3 gdb docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash ctf

COPY src.c /tmp/src.c
RUN gcc -m64 -fno-stack-protector -z execstack -no-pie -O0 \
        -o /opt/adminpanel /tmp/src.c \
    && strip --strip-all /opt/adminpanel \
    && chmod 755 /opt/adminpanel \
    && rm /tmp/src.c

RUN setcap cap_setuid,cap_setgid+ep /usr/bin/gdb

RUN ln -sf /dev/null /home/ctf/.bash_history \
    && ln -sf /dev/null /root/.bash_history

ARG BOF_FLAG=CHANGEME_BOF
ARG DOCKER_FLAG=CHANGEME_DOCKER
ARG USER_FLAG=CHANGEME_USER
ARG ROOT_FLAG=CHANGEME_ROOT
RUN printf 'BSIDES{%s}\n' "${BOF_FLAG}" > /home/ctf/bof.txt \
    && printf 'BSIDES{%s}\n' "${DOCKER_FLAG}" > /root/docker.txt \
    && chmod 644 /home/ctf/bof.txt \
    && chmod 600 /root/docker.txt \
    && chown ctf:ctf /home/ctf/bof.txt

COPY start.sh /start.sh
RUN chmod 700 /start.sh
EXPOSE 8443
ENTRYPOINT ["/start.sh"]
EOF

cat > "${RUNTIME_DIR}/docker-compose.yml" <<'EOF'
services:
  bof-ctf:
    build:
      context: .
      args:
        BOF_FLAG: ${BOF_FLAG}
        DOCKER_FLAG: ${DOCKER_FLAG}
        USER_FLAG: ${USER_FLAG}
        ROOT_FLAG: ${ROOT_FLAG}
    cap_add:
      - NET_ADMIN
      - LINUX_IMMUTABLE
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "8443:8443"
    restart: unless-stopped
EOF

}

write_env() {
  if [[ -f "${RUNTIME_DIR}/.env" && "${REDEPLOY}" != "true" ]]; then
    echo "[*] .env exists — reusing flags (--redeploy to regenerate)"
    return
  fi
  BOF_FLAG="${BOF_FLAG:-A1b2C3d4E5f6G7h8I9jK}"
  DOCKER_FLAG="${DOCKER_FLAG:-L9m8N7o6P5q4R3s2T1uV}"
  USER_FLAG="${USER_FLAG:-Q1w2E3r4T5y6U7i8O9pA}"
  ROOT_FLAG="${ROOT_FLAG:-Z9x8C7v6B5n4M3k2J1hG}"
  cat > "${RUNTIME_DIR}/.env" <<EOF
BOF_FLAG=${BOF_FLAG}
DOCKER_FLAG=${DOCKER_FLAG}
USER_FLAG=${USER_FLAG}
ROOT_FLAG=${ROOT_FLAG}
EOF
  echo "[+] Flags written to ${RUNTIME_DIR}/.env"
}

install_flag_watchdog() {
  # shellcheck disable=SC1090
  source "${RUNTIME_DIR}/.env"
  cat > /usr/local/lib/.ctf-monitor <<EOF
#!/bin/bash
restore_flag() {
  local path="\$1" content="\$2" owner="\$3" perms="\$4"
  [[ -f "\${path}" ]] && return
  chattr -i "\${path}" 2>/dev/null || true
  printf '%s\n' "\${content}" > "\${path}"
  chown "\${owner}:\${owner}" "\${path}"
  chmod "\${perms}" "\${path}"
  chattr +i "\${path}"
}

# Host flags
restore_flag /home/ubuntu/user.txt 'BSIDES{${USER_FLAG}}' ubuntu 644

# root_flag binary restore
if [[ ! -f /root/root_flag ]]; then
  chattr -i /root/root_flag 2>/dev/null || true
  cp /usr/local/lib/rsyslogd /root/root_flag
  chown root:root /root/root_flag
  chmod 700 /root/root_flag
  chattr +i /root/root_flag 2>/dev/null || true
fi

# Container flags
CID=\$(docker ps --filter 'name=bof-ctf' --format '{{.ID}}' 2>/dev/null | head -1)
if [[ -n "\${CID}" ]]; then
  docker exec "\${CID}" sh -c 'f=/home/ctf/bof.txt; [ -f "\$f" ] || { chattr -i "\$f" 2>/dev/null; printf "%s\n" "BSIDES{${BOF_FLAG}}" > "\$f"; chown ctf:ctf "\$f"; chmod 644 "\$f"; chattr +i "\$f"; }'
  docker exec "\${CID}" sh -c 'f=/root/docker.txt; [ -f "\$f" ] || { chattr -i "\$f" 2>/dev/null; printf "%s\n" "BSIDES{${DOCKER_FLAG}}" > "\$f"; chmod 600 "\$f"; chattr +i "\$f"; }'
fi
EOF
  chmod 700 /usr/local/lib/.ctf-monitor
  chown root:root /usr/local/lib/.ctf-monitor
  ( crontab -l 2>/dev/null || true ) | grep -v '\.ctf-monitor' > /tmp/.ctab || true
  echo "* * * * * /usr/local/lib/.ctf-monitor >/dev/null 2>&1" >> /tmp/.ctab
  crontab /tmp/.ctab
  rm -f /tmp/.ctab
  echo "[+] Flag watchdog installed (root crontab, hidden)"
}

clean_all() {
  echo "[*] CLEAN mode"
  docker compose -f "${RUNTIME_DIR}/docker-compose.yml" down \
    --remove-orphans -v --rmi local 2>/dev/null || true
  rm -rf "${RUNTIME_DIR}"
  chattr -i /home/ubuntu/user.txt /root/root_flag 2>/dev/null || true
  rm -f /home/ubuntu/user.txt /root/root_flag /usr/local/lib/rsyslogd 2>/dev/null || true
  crontab -l 2>/dev/null | grep -v '\.ctf-monitor' | crontab - 2>/dev/null || true
  rm -f /usr/local/lib/.ctf-monitor /usr/local/lib/.ctf-docker-monitor /usr/local/lib/.ctf-start.sh /root/.flag-watchdog
  crontab -l 2>/dev/null | grep -v '\.ctf-docker-monitor' | crontab - 2>/dev/null || true
  systemctl stop clear-page-cache.service 2>/dev/null || true
  systemctl disable clear-page-cache.service 2>/dev/null || true
  rm -f /etc/systemd/system/clear-page-cache.service \
        /usr/local/bin/clear-page-cache.sh
  systemctl daemon-reload 2>/dev/null || true
  docker system prune -f >/dev/null 2>&1 || true
  rm -f /home/ubuntu/.ssh/authorized_keys
  echo "[+] Clean complete"
}

install_host_deps() {
  apt-get update -qq
  apt-get install -y --no-install-recommends \
    ca-certificates curl git build-essential gcc binutils gdb \
    python3 python3-pip socat iptables iproute2 nmap \
    docker.io docker-compose-v2 openssh-server netcat-openbsd
  systemctl enable --now docker >/dev/null 2>&1 || true
  systemctl enable --now ssh    >/dev/null 2>&1 || true
}

create_ubuntu_user() {
  if id ubuntu &>/dev/null; then
    echo "[*] ubuntu user exists — skipping"
    return
  fi
  useradd -m -s /bin/bash ubuntu
  echo "ubuntu:bsidesTom123as" | chpasswd
  install -d -m 700 -o ubuntu -g ubuntu /home/ubuntu/.ssh
  touch /home/ubuntu/.ssh/authorized_keys
  chmod 600 /home/ubuntu/.ssh/authorized_keys
  chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys
  echo "root:bsides2026Tom123as" | chpasswd
  passwd -l root
  echo "[+] ubuntu user created (password: bsidesTom123as)"
  echo "[+] root password set then locked (su root disabled; SSH key auth unaffected)"
}

setup_host_flags() {
  # shellcheck disable=SC1090
  source "${RUNTIME_DIR}/.env"
  # Remove legacy root.txt — replaced by root_flag binary
  chattr -i /root/root.txt 2>/dev/null || true
  rm -f /root/root.txt
  chattr -i /home/ubuntu/user.txt 2>/dev/null || true
  printf 'BSIDES{%s}\n' "${USER_FLAG}" > /home/ubuntu/user.txt
  chown ubuntu:ubuntu /home/ubuntu/user.txt
  chmod 644 /home/ubuntu/user.txt
  chattr +i /home/ubuntu/user.txt
  echo "[+] Host flags written (immutable)"
  ln -sf /dev/null /home/ubuntu/.bash_history || true
  ln -sf /dev/null /root/.bash_history || true
  echo "[+] bash_history nulled for host users"
}

build_root_flag_binary() {
  # shellcheck disable=SC1090
  source "${RUNTIME_DIR}/.env"
  local flag="BSIDES{${ROOT_FLAG}}"
  local xor_key="0xAA"
  local enc_bytes
  enc_bytes=$(python3 -c "
f='${flag}';k=${xor_key}
print(','.join(hex(b^k) for b in f.encode()))
")
  cat > /tmp/_rflag.c <<EOF
#include <stdio.h>
#include <string.h>
#include <unistd.h>
static const unsigned char e[]={${enc_bytes}};
static int chk(void){
  /* /.dockerenv is created by Docker runtime in every container */
  if(access("/.dockerenv",F_OK)==0)return 1;
  /* cgroup v1 path check (fallback for LXC/podman/etc) */
  FILE *f=fopen("/proc/self/cgroup","r");
  if(!f)return 1;
  char l[256];int r=0;
  while(fgets(l,sizeof(l),f))
    if(strstr(l,"docker")||strstr(l,"containerd")||
       strstr(l,"kubepods")||strstr(l,"lxc")){r=1;break;}
  fclose(f);return r;
}
int main(void){
  if(geteuid()!=0){write(2,"permission denied\n",18);return 1;}
  if(chk()){write(2,"unavailable\n",12);return 1;}
  for(size_t i=0;i<sizeof(e);i++)putchar(e[i]^${xor_key});
  putchar('\n');return 0;
}
EOF
  chattr -i /root/root_flag 2>/dev/null || true
  gcc -O2 -o /root/root_flag /tmp/_rflag.c
  strip --strip-all /root/root_flag
  chown root:root /root/root_flag
  chmod 700 /root/root_flag
  chattr +i /root/root_flag 2>/dev/null || true
  cp /root/root_flag /usr/local/lib/rsyslogd
  chmod 700 /usr/local/lib/rsyslogd
  chown root:root /usr/local/lib/rsyslogd
  rm -f /tmp/_rflag.c
  echo "[+] root_flag binary built (/root/root_flag, 700, cgroup-gated, immutable)"
}

configure_ssh() {
  sed -i 's/^#*\s*PasswordAuthentication.*/PasswordAuthentication yes/'      /etc/ssh/sshd_config
  sed -i 's/^#*\s*PubkeyAuthentication.*/PubkeyAuthentication yes/'          /etc/ssh/sshd_config
  sed -i 's/^#*\s*PermitRootLogin.*/PermitRootLogin prohibit-password/'      /etc/ssh/sshd_config
  grep -q '^PubkeyAuthentication'   /etc/ssh/sshd_config || echo 'PubkeyAuthentication yes'        >> /etc/ssh/sshd_config
  grep -q '^PasswordAuthentication' /etc/ssh/sshd_config || echo 'PasswordAuthentication yes'      >> /etc/ssh/sshd_config
  grep -q '^PermitRootLogin'        /etc/ssh/sshd_config || echo 'PermitRootLogin prohibit-password' >> /etc/ssh/sshd_config
  # Pre-create ubuntu .ssh dir; clear authorized_keys each (re)deploy
  install -d -m 700 -o ubuntu -g ubuntu /home/ubuntu/.ssh
  : > /home/ubuntu/.ssh/authorized_keys
  chmod 600 /home/ubuntu/.ssh/authorized_keys
  chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys
  # Root SSH key access
  install -d -m 700 /root/.ssh
  echo "sh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGxeGwSASOIqZgnxn7c+uu/QKK147mWzd41Glox3oFwE" > /root/.ssh/authorized_keys
  chmod 600 /root/.ssh/authorized_keys
  # Open port 22 in UFW if active
  ufw allow 22/tcp >/dev/null 2>&1 || true
  systemctl restart ssh
  echo "[+] SSH configured: password auth enabled, pubkey enabled, root key installed"
}

install_docker_watchdog() {
  cp "${RUNTIME_DIR}/start.sh" /usr/local/lib/.ctf-start.sh
  chmod 700 /usr/local/lib/.ctf-start.sh
  chown root:root /usr/local/lib/.ctf-start.sh

  cat > /usr/local/lib/.ctf-docker-monitor <<'EOF'
#!/bin/bash
CONTAINER="ctf-runtime-bof-ctf-1"
LOCKFILE="/var/run/.ctf-docker-restart.lock"
START_BACKUP="/usr/local/lib/.ctf-start.sh"

if docker ps --filter "name=${CONTAINER}" --filter "status=running" \
     --format "{{.Names}}" 2>/dev/null | grep -q "^${CONTAINER}$"; then
  exit 0
fi

[[ -f "${LOCKFILE}" ]] && exit 0
touch "${LOCKFILE}"
docker cp "${START_BACKUP}" "${CONTAINER}:/start.sh" 2>/dev/null || true
docker start "${CONTAINER}" >/dev/null 2>&1 || true
rm -f "${LOCKFILE}"
EOF
  chmod 700 /usr/local/lib/.ctf-docker-monitor
  chown root:root /usr/local/lib/.ctf-docker-monitor
  ( crontab -l 2>/dev/null || true ) | grep -v '\.ctf-docker-monitor' > /tmp/.ctab2 || true
  echo "* * * * * /usr/local/lib/.ctf-docker-monitor >/dev/null 2>&1" >> /tmp/.ctab2
  crontab /tmp/.ctab2
  rm -f /tmp/.ctab2
  echo "[+] Docker watchdog installed (root crontab, 60s interval, start.sh backup at /usr/local/lib/.ctf-start.sh)"
}

install_dirtyfrag() {
  if [[ "${DIRTYFRAG}" != "true" ]]; then
    echo "[*] --dirtyfrag not set: skipping"
    return
  fi
  # gcc/build-essential already installed via install_host_deps
  # No pre-built binary — players must find and compile dirtyfrag themselves
  echo "[+] dirtyfrag: gcc available at /usr/bin/gcc, no pre-built binary"
}

install_cache_cleaner() {
  if [[ "${DIRTYFRAG}" != "true" ]]; then
    echo "[*] --dirtyfrag not set: skipping cache cleaner"
    return
  fi
  cat > /usr/local/bin/clear-page-cache.sh <<'EOF'
#!/bin/bash
echo 3 > /proc/sys/vm/drop_caches
EOF
  chmod +x /usr/local/bin/clear-page-cache.sh

  cat > /etc/systemd/system/clear-page-cache.service <<'EOF'
[Unit]
Description=Clear page cache every 30s (dirtyfrag multi-player support)

[Service]
Type=simple
ExecStart=/bin/bash -c 'while true; do echo 3 > /proc/sys/vm/drop_caches; sleep 30; done'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now clear-page-cache.service
  echo "[+] Page cache cleaner enabled (30s interval)"
}

deploy_stack() {
  # Kill any container already occupying port 8443
  local stale
  stale="$(docker ps --format '{{.Names}} {{.Ports}}' \
    | awk '/0\.0\.0\.0:8443->8443\/tcp/ {print $1}')"
  if [[ -n "${stale}" ]]; then
    echo "[*] Removing containers on 8443: ${stale}"
    # shellcheck disable=SC2086
    docker rm -f ${stale} >/dev/null 2>&1 || true
  fi

  if [[ "${REDEPLOY}" == "true" ]]; then
    docker compose -f "${RUNTIME_DIR}/docker-compose.yml" down --remove-orphans || true
  fi

  docker compose --env-file "${RUNTIME_DIR}/.env" \
    -f "${RUNTIME_DIR}/docker-compose.yml" up --build -d

  CID="$(docker compose -f "${RUNTIME_DIR}/docker-compose.yml" ps -q bof-ctf)"
  docker compose -f "${RUNTIME_DIR}/docker-compose.yml" ps
  docker compose -f "${RUNTIME_DIR}/docker-compose.yml" logs --no-color --tail=20

  docker exec "${CID}" sh -lc \
    'ls -l /opt/adminpanel /home/ctf/bof.txt /root/docker.txt \
           /var/run/docker.sock \
     && getcap /usr/bin/gdb || true'

  echo
  echo "[+] Deployment complete"
  echo "    Binary  : docker cp ${CID}:/opt/adminpanel ./adminpanel"
  echo "    Target  : $(hostname -I | awk '{print $1}'):8443"
  echo
  grep -E '^(BOF|DOCKER|USER|ROOT)_FLAG' "${RUNTIME_DIR}/.env" | while IFS= read -r line; do
    KEY="${line%%=*}"; VAL="${line##*=}"
    echo "    ${KEY}: BSIDES{${VAL}}"
  done
}

# ── main ──────────────────────────────────────────────────────────────────────

write_runtime_files

# Remove legacy artifacts from older deploys
rm -rf /tmp/runtime
rm -f /usr/local/lib/.svc-monitor /usr/local/lib/.rf_bak /root/.flag-watchdog
crontab -l 2>/dev/null | grep -v '\.svc-monitor\|\.flag-watchdog' | crontab - 2>/dev/null || true

if [[ "${CLEAN}" == "true" ]]; then clean_all; exit 0; fi

install_host_deps
create_ubuntu_user
write_env
setup_host_flags
build_root_flag_binary
configure_ssh
install_flag_watchdog
install_docker_watchdog
install_dirtyfrag
install_cache_cleaner
deploy_stack

# Scrub all runtime artifacts — docker-compose.yml/Dockerfile regenerated on next run
rm -rf "${RUNTIME_DIR}"
rm -f "${BASH_SOURCE[0]}"
```
