#!/usr/bin/env bash
# Connect this cloud session to the CK2 test box: NetBird in userspace (netstack, no TUN needed),
# then an `ssh ck2box` alias through its SOCKS listener. Run as root; idempotent, so a resumed
# session can run it again. Needs CK2_BOX_NETBIRD_SETUP_KEY, CK2_BOX_SSH_KEY_B64 and
# CK2_BOX_KNOWN_HOSTS in the environment; never print them.
# From senomorf/homelab#2440 (the box's side, private). CK2_BOX_PROBE=0 skips the closing
# `ssh ck2box box-status`, which the session start hook uses so that a session doesn't start the
# box (it shares the CI runner's memory) before it needs it.
set -euo pipefail
NETBIRD_VERSION=0.82.1
NETBIRD_SHA256=c8f10b89dfa01b8bcad5ec25b666a83e351be4e22eb784b822478b9326a35423
: "${CK2_BOX_NETBIRD_SETUP_KEY:?missing}" "${CK2_BOX_SSH_KEY_B64:?missing}" "${CK2_BOX_KNOWN_HOSTS:?missing}"
dir=${CK2_BOX_DIR:-/var/lib/ck2box} port=${CK2_BOX_SOCKS_PORT:-1080}
sock=unix://$dir/netbird.sock
install -d -m 0700 "$dir"
if ! [ -x "$dir/netbird" ] || [ "$("$dir/netbird" version 2>/dev/null)" != "$NETBIRD_VERSION" ]; then
	tmp=$(mktemp -d)
	curl -fsSL -o "$tmp/nb.tgz" "https://github.com/netbirdio/netbird/releases/download/v$NETBIRD_VERSION/netbird_${NETBIRD_VERSION}_linux_amd64.tar.gz"
	echo "$NETBIRD_SHA256  $tmp/nb.tgz" | sha256sum -c --quiet -
	tar -xzf "$tmp/nb.tgz" -C "$tmp" netbird
	install -m 0755 "$tmp/netbird" "$dir/netbird"
	rm -rf "$tmp"
fi
nb() { "$dir/netbird" "$@" --daemon-addr "$sock"; }
if ! nb status >/dev/null 2>&1; then
	# NB_DISABLE_SSH_CONFIG: otherwise NetBird writes an ssh_config.d file that turns off host-key
	# checks for every peer.
	env NB_STATE_DIR="$dir/state" NB_USE_NETSTACK_MODE=true NB_NETSTACK_SKIP_PROXY=false \
		NB_SOCKS5_LISTENER_ADDRESS=127.0.0.1 NB_SOCKS5_LISTENER_PORT="$port" \
		NB_DISABLE_SSH_CONFIG=true NB_FORCE_RELAY=true \
		setsid "$dir/netbird" service run --config "$dir/config.json" --daemon-addr "$sock" \
		--log-file "$dir/netbird.log" </dev/null >/dev/null 2>&1 &
	for _ in $(seq 50); do nb status >/dev/null 2>&1 && break; sleep 0.2; done
fi
if ! nb status 2>/dev/null | grep -q '^Management: Connected'; then
	kf=$(mktemp)
	printf '%s' "$CK2_BOX_NETBIRD_SETUP_KEY" >"$kf"
	nb up --setup-key-file "$kf" --hostname "ck2-session-$(date +%s)" \
		--disable-dns --disable-client-routes --disable-server-routes >/dev/null || { rm -f "$kf"; exit 1; }
	rm -f "$kf"
fi
# ssh reads the passwd entry's home, not $HOME.
home=$(getent passwd "$(id -u)" | cut -d: -f6)
install -d -m 0700 "$home/.ssh"
printf '%s' "$CK2_BOX_SSH_KEY_B64" | base64 -d >"$home/.ssh/ck2box"
chmod 0600 "$home/.ssh/ck2box"
printf '%s\n' "$CK2_BOX_KNOWN_HOSTS" >"$home/.ssh/ck2box_known_hosts"
hp=${CK2_BOX_KNOWN_HOSTS%% *} # [address]:port
host=${hp#[}; host=${host%%]*}; p=${hp##*]:}
cat >"$home/.ssh/ck2box.conf" <<EOF
Host ck2box
  HostName $host
  Port $p
  User ck2box
  IdentityFile $home/.ssh/ck2box
  IdentitiesOnly yes
  UserKnownHostsFile $home/.ssh/ck2box_known_hosts
  StrictHostKeyChecking yes
  BatchMode yes
  ConnectTimeout 30
  ServerAliveInterval 15
  ControlMaster auto
  ControlPath /tmp/ck2box-%C
  ControlPersist 10m
  ProxyCommand nc -X 5 -x 127.0.0.1:$port %h %p
EOF
# The Include has to come before any Host block, or it applies only inside that block.
if ! grep -qxF "Include $home/.ssh/ck2box.conf" "$home/.ssh/config" 2>/dev/null; then
	{ echo "Include $home/.ssh/ck2box.conf"; cat "$home/.ssh/config" 2>/dev/null || true; } >"$home/.ssh/config.new"
	mv "$home/.ssh/config.new" "$home/.ssh/config"
	chmod 0600 "$home/.ssh/config"
fi
[ "${CK2_BOX_PROBE:-1}" != 0 ] || exit 0
# The relayed path to the box can take a few seconds to come up after enrolment.
for _ in $(seq 20); do
	if ssh ck2box box-status; then exit 0; fi
	sleep 3
done
echo "box-connect: the box did not answer; see $dir/netbird.log" >&2
exit 1
