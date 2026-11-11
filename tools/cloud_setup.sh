#!/bin/bash
# Setup script for the "ck2-mod-dev" Claude cloud environment.
# Paste into: environment settings > Setup script. Runs as root when a
# container is built fresh. Installs the .NET 9 SDK and the CWTools CLI.
# Each step is optional: failures are logged and never stop the session.
# The repo's own tools need only Python 3, already in the image.
set -u
log() { echo "[ck2-setup] $*"; }
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1

if ! command -v dotnet >/dev/null 2>&1; then
  if curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh \
    && bash /tmp/dotnet-install.sh --channel 9.0 --install-dir /usr/share/dotnet >/dev/null; then
    ln -sf /usr/share/dotnet/dotnet /usr/local/bin/dotnet
    log "installed .NET $(dotnet --version)"
  else
    log "could not install .NET 9; CWTools CLI skipped"
  fi
fi

if command -v dotnet >/dev/null 2>&1 && ! command -v cwtools >/dev/null 2>&1; then
  if dotnet tool install --tool-path /opt/cwtools CWTools.CLI --version 0.6.0-alpha >/dev/null; then
    ln -sf /opt/cwtools/cwtools /usr/local/bin/cwtools
    log "installed CWTools CLI"
  else
    log "could not install CWTools CLI"
  fi
fi

exit 0
