# Allied Fleets

Lets a ruler at war ask an ally for ships. CK2 doesn't let armies board an ally's ships (engine behaviour, per player reports). So instead of sharing a fleet, the ally "lends" one: the requester gets a temporary fleet of their own.

## What it adds

- Targeted decision **Request Ships** (`afl_request_ships`), on an ally's diplomacy screen. It's available while you are at war, have 50 gold, have no lent fleet already, and have no request pending.
- Event `afl.1` for the ally: lend (you pay them 50 gold) or refuse. AI allies lend 75% of the time.
- On lend, you get 20 galleys in the sea zone nearest you, earmarked `afl_lent_ships`. They disband when your war ends. Size and terms copy vanilla's Conscript Merchant Ships (`vanilla/decisions/unit_decisions.txt`).
- Events `afl.2` and `afl.3` tell you the answer.

The ally's own ships are not affected. The mod only creates new ships for you.

## Files

- `decisions/afl_decisions.txt`, `events/afl_events.txt`, `localisation/afl_localisation.csv`. It overrides no vanilla files.
- `common/scripted_triggers/afl_triggers.txt` holds the decision's conditions (`afl_can_request_ships_trigger`), and `common/scripted_effects/afl_effects.txt` holds each step: ask (`afl_ask_for_ships_effect`), lend (`afl_lend_ships_effect`) and refuse (`afl_refuse_ships_effect`). The decision and `afl.1`'s options call them, and so do the in-game tests in `tests/game/allied_fleets/`, so the tests run the same code players do (#38).

## Log lines

Each step writes an `afl:` line to `game.log`, for example `afl: lent 20 galleys from <ally> (<id>) to <requester> (<id>) for 50 gold`. [Unverified] They appear only when the game runs with `-debugscripts` or `-scriptlog` (per `vanilla/ChangeLog.txt`), so normal play shows nothing. To include them in a bug report, add `-scriptlog` to the game's Steam launch options and send `Documents/Paradox Interactive/Crusader Kings II/logs/game.log`.

## Save compatibility

It adds only a decision, events, localisation, a character flag and an earmark. [Inference] It should load into an existing save, and removing it later should leave at most a stray flag or earmarked fleet. This is not yet tested.

## Multiplayer

Every player needs the same version, because the checksum changes. AI never takes the decision (`ai = no`), but AI allies answer requests.

## Open design questions

1. Cost: 50 gold from requester to ally. Should the ally pay instead, or should it cost prestige or nothing?
2. Size: a fixed 20 galleys. Should it scale with the requester's army? Vanilla's `spawn_fleet` has `match_character`/`match_mult`, but I haven't confirmed what they scale by.
3. Limits: should it require that you and the ally fight in the same war, not just any war?
4. Should the ally need ships of their own, a coast, or a minimum naval size?
