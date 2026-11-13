#!/bin/bash
# Container setup for Claude cloud sessions on ck2-mods. Runs as root when a
# container is built fresh, from the environment's setup script:
#
#   [ -f ck2-mods/tools/cloud_setup.sh ] && bash ck2-mods/tools/cloud_setup.sh; exit 0
#
# Usage: tools/cloud_setup.sh [step ...]   (no step: all of them)
# Steps:
#   - depotdownloader: downloads the game's files from Steam (tools/steam_fetch_vanilla.py)
#   - dotnet, cwtools: .NET 9 SDK + CWTools CLI, optional extra validation (lint.py --cwtools)
#   - shellcheck, actionlint: the linters CI's lint job runs; lint.yml installs them with these
#     steps, so a session checks with the same versions
# Each step is optional: failures are logged and never stop the session.
# Safe to run again: installed tools are skipped.
set -u
log() { echo "[ck2-setup] $*"; }

DEPOTDOWNLOADER_VERSION=3.4.0
CWTOOLS_CLI_VERSION=0.6.0-alpha
SHELLCHECK_VERSION=0.11.0
ACTIONLINT_VERSION=1.7.12
DOTNET_CHANNEL=9.0
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1

install_depotdownloader() {
  local dir=/opt/depotdownloader
  if [ -x "$dir/DepotDownloader" ] && [ "$(cat "$dir/VERSION" 2>/dev/null)" = "$DEPOTDOWNLOADER_VERSION" ]; then
    return 0
  fi
  local url="https://github.com/SteamRE/DepotDownloader/releases/download/DepotDownloader_${DEPOTDOWNLOADER_VERSION}/DepotDownloader-linux-x64.zip"
  local tmp; tmp="$(mktemp -d)"
  if curl -fsSL "$url" -o "$tmp/dd.zip" && python3 -I -m zipfile -e "$tmp/dd.zip" "$tmp/out"; then
    rm -rf "$dir" && mkdir -p "$dir" && cp -r "$tmp/out/." "$dir/"
    chmod +x "$dir/DepotDownloader"
    echo "$DEPOTDOWNLOADER_VERSION" > "$dir/VERSION"
    ln -sf "$dir/DepotDownloader" /usr/local/bin/DepotDownloader
    log "installed DepotDownloader $DEPOTDOWNLOADER_VERSION"
  else
    log "could not install DepotDownloader; game files can't be fetched from Steam"
  fi
  rm -rf "$tmp"
}

install_dotnet() {
  command -v dotnet >/dev/null 2>&1 && return 0
  if curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh \
    && bash /tmp/dotnet-install.sh --channel "$DOTNET_CHANNEL" --install-dir /usr/share/dotnet >/dev/null; then
    ln -sf /usr/share/dotnet/dotnet /usr/local/bin/dotnet
    log "installed .NET $(dotnet --version)"
  else
    log "could not install .NET $DOTNET_CHANNEL; CWTools CLI skipped"
  fi
}

install_cwtools() {
  command -v dotnet >/dev/null 2>&1 || return 0
  command -v cwtools >/dev/null 2>&1 && return 0
  if dotnet tool install --tool-path /opt/cwtools CWTools.CLI --version "$CWTOOLS_CLI_VERSION" >/dev/null; then
    ln -sf /opt/cwtools/cwtools /usr/local/bin/cwtools
    log "installed CWTools CLI $CWTOOLS_CLI_VERSION"
  else
    log "could not install CWTools CLI"
  fi
}

# install_release NAME VERSION URL MEMBER: one binary from a .tar.gz release into /usr/local/bin,
# skipped when that version is already there.
install_release() {
  local name=$1 version=$2 url=$3 member=$4 bin=/usr/local/bin/$1
  if [ -x "$bin" ] && "$bin" --version 2>/dev/null | grep -qF "$version"; then
    return 0
  fi
  local tmp; tmp="$(mktemp -d)"
  if curl -fsSL "$url" -o "$tmp/a.tgz" && tar -xzf "$tmp/a.tgz" -C "$tmp" "$member" \
    && install -m 0755 "$tmp/$member" "$bin"; then
    log "installed $name $version"
  else
    log "could not install $name $version"
  fi
  rm -rf "$tmp"
}

install_shellcheck() {
  local v=$SHELLCHECK_VERSION
  install_release shellcheck "$v" \
    "https://github.com/koalaman/shellcheck/releases/download/v$v/shellcheck-v$v.linux.x86_64.tar.gz" \
    "shellcheck-v$v/shellcheck"
}

install_actionlint() {
  local v=$ACTIONLINT_VERSION
  install_release actionlint "$v" \
    "https://github.com/rhysd/actionlint/releases/download/v$v/actionlint_${v}_linux_amd64.tar.gz" \
    actionlint
}

steps=("$@")
[ "${#steps[@]}" -gt 0 ] || steps=(depotdownloader dotnet cwtools shellcheck actionlint)
for step in "${steps[@]}"; do
  case $step in
    depotdownloader) install_depotdownloader ;;
    dotnet) install_dotnet ;;
    cwtools) install_cwtools ;;
    shellcheck) install_shellcheck ;;
    actionlint) install_actionlint ;;
    *) log "unknown step: $step" ;;
  esac
done
exit 0
