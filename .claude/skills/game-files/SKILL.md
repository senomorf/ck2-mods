---
name: game-files
description: Get CK2's own game files into vanilla/ for a cloud session, downloading them from the user's Steam account with a QR login when no cached copy exists.
---

# Game files (vanilla/)

The session hook unpacks the cached copy automatically. Do this only when `vanilla/` is missing and the user wants it, or the cache is stale.

## 1. Check the cache

- `ls -la /mnt/project-files/ck2-vanilla/` and read `ck2-game-files.json` (date, file count, depot manifests).
- If the zip exists: `tools/fetch_vanilla.sh /mnt/project-files/ck2-vanilla/ck2-game-files.zip`. Done.

## 2. Download from Steam (needs the user, once)

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
