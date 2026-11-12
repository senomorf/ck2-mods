#!/bin/bash
# Container setup for Claude cloud sessions on ck2-mods. Runs as root when a
# container is built fresh, from the environment's setup script:
#
#   [ -f ck2-mods/tools/cloud_setup.sh ] && bash ck2-mods/tools/cloud_setup.sh; exit 0
#
# Installs:
#   - DepotDownloader: downloads the game's files from Steam (tools/steam_fetch_vanilla.py)
#   - .NET 9 SDK + CWTools CLI: optional extra validation (tools/cwtools_check.py, lint.py --cwtools)
# Each step is optional: failures are logged and never stop the session.
# Safe to run again: installed tools are skipped.
set -u
log() { echo "[ck2-setup] $*"; }

DEPOTDOWNLOADER_VERSION=3.4.0
CWTOOLS_CLI_VERSION=0.6.0-alpha
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

install_depotdownloader
install_dotnet
install_cwtools
exit 0
