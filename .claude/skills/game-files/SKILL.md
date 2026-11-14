---
name: game-files
description: Get CK2's own game files into vanilla/ for a cloud session, from the cached zip in project files, a zip the user uploads, or (fallback) a Steam QR login.
---

# Game files (vanilla/)

The session hook unpacks the cached copy automatically. Do this only when `vanilla/` is missing and the user wants it, or the cache is stale.

## 1. Check the cache

- `ls -la /mnt/project-files/ck2-vanilla/` and read `ck2-game-files.json` (date, file count, depot manifests).
- If the zip exists: `tools/fetch_vanilla.sh /mnt/project-files/ck2-vanilla/ck2-game-files.zip`. Done.

## 2. Ask the user for a zip (preferred)

The user prefers uploading over Steam logins (2026-11-12). Ask them to zip these folders from the CK2 install folder (Steam > Crusader Kings II > Manage > Browse local files): `common`, `decisions`, `events`, `history`, `interface`, `localisation`, plus `map/*.txt|csv|map` if handy. The 3.3.5.1 zip was 17 MB. Take the version from the main menu's bottom-left label (`3.3.5.1 (SOHY)`), not `ChangeLog.txt`, which stops at 3.3.3. Copy the upload to `/mnt/project-files/ck2-vanilla/ck2-game-files.zip`, write `ck2-game-files.json` beside it (files, sha256, game version), and unpack with `tools/fetch_vanilla.sh`.

## 3. Download from Steam (fallback, needs the user)

Does not work from a Claude cloud session (checked 2026-11-12): the agent proxy does not carry WebSocket or raw TCP connections, which Steam login needs (`/root/.ccr/README.md`, "Not supported through the proxy"). The steps below only apply on a machine with direct internet access.

Requires the `ck2-mod-dev` environment (unrestricted network) with `DepotDownloader` installed by `tools/cloud_setup.sh`. Check with `command -v DepotDownloader`.

1. Tell the user a QR code is coming and they need the Steam mobile app open (Steam Guard > scan QR). Ask whether to keep the Steam session token for later runs (`--keep-login`); default is no. Kept, it sits in the project's shared files and lets anyone with access to them download with their account.
2. Start the download in the background: `python3 tools/steam_fetch_vanilla.py --qr` (add `--keep-login` if they agreed).
3. Wait for the output line `QR code ready: /mnt/project-files/ck2-cache/steam-login-qr.png`, then post that file to the user right away. If the output says the QR code changed, post the new image.
4. When the run finishes, it prints the zip path. Unpack it with `tools/fetch_vanilla.sh <zip>` and tell the user how many files were cached.
5. With a kept session, later runs need no QR: `python3 tools/steam_fetch_vanilla.py --username <account name>` (the name is printed after the first login).

On failure read `/mnt/project-files/ck2-cache/last-run.log`. Repeated failed logins can trigger Steam's rate limit for an hour or more; don't retry in a loop.

## Rules

- Never ask for or handle the user's Steam password. QR login only.
- Never commit, upload elsewhere, or quote large parts of the files. They are Paradox's content.
