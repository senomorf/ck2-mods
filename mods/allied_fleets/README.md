# Allied Fleets

Lets a ruler borrow part of another ruler's fleet: for crusades and other wars overseas, and above all for landlocked players in multiplayer. CK2 lets an army board only its own ruler's ships (engine behaviour, per player reports in #8), so the borrower gets a fleet of its own, and the lender's fleet at home shrinks by the same share while it is away.

**Status:** this is the design for v0.1, agreed with the owner on 2026-11-14 (issue #8; discussion and sources in the design doc linked there). The script in this folder is still the old prototype, which v0.1 replaces. Nothing below has been tested in game.

## How it worked in reality

Rulers who needed ships hired them, with their crews, by contract. The contract set the men and horses to carry, a price, a term, a port and a date. Venice's 1201 contract for the Fourth Crusade carried 33,500 men for one year at four marks per horse and two per man, and Venice added fifty galleys of its own for half the conquests (Villehardouin). Allies in the same war sailed with the army; everyone else bought passage. The design doc lists the sources.

## Design

Option C of the design doc: one contract, with war-loan terms for allies and war partners, and charter terms for anyone else.

### Who may lend and borrow

- **Borrower:** any playable ruler. No port is needed: armies board ships at sea from any coast.
- **Lender:** a ruler with a port in its realm.
- **War loan (step 1):** the two are allied, or on the same side of a war (crusade partners are temporary war allies, whom `is_allied_with` misses).
- **Charter (step 2):** anyone not at war with the lender.
- One contract per ruler at a time, as borrower or as lender. Nobody lends and borrows at once, so two allies can't trade fleets to avoid paying for their own.
- No lending while the lender's own fleet is raised, so the same ships can't serve twice. This needs a trigger that sees a raised fleet: in probes neither `any_army` nor `has_raised_levies` saw a spawned fleet, and whether `has_raised_levies` sees a raised one is still to test. If nothing does, this rule goes.

### What is lent

- **A share of the lender's fleet:** a quarter or a half (owner's choice, 2026-11-14). The borrower's fleet is spawned with `match_character` = the lender and `match_mult` = the share. No script can count ships, so a share is the only size that keeps the lender's loss equal to what it lends.
- **Where it appears:** a war loan appears at once, near the borrower; a charter, after assembly, in the lender's port.
- **Ships away:** every port in the lender's realm, vassals' ports included, carries a "Ships away" province modifier (negative `galleys_perc`) while the contract runs. Percentages add to the province's other bonuses: in probes a holding's galleys came to its base times (1.2 plus the modifiers), so −50% cut Venice's fleet by 42% and −60% cut Zadar's by 50%. [Inference] While that 1.2 holds, a quarter needs −30% and a half −60%. A flat `galleys = -10` took 10 off each holding before the 1.2 and emptied the small ones, and `galleys_max_levy` is not a modifier the game accepts, so a percentage it is.
- **Vassals mind:** vassals whose ports carry it get an opinion penalty while it lasts. Their ships serve their liege, not the liege's customers.
- **The lent fleet keeps its size.** If the lender loses ports or shipyards, its home fleet takes the loss.

### Payment

- **Crew wages:** the fleet's normal upkeep, charged by the game to the borrower, as for its own ships. `spawn_fleet` takes `maintenance_multiplier`: in a probe, 50 galleys spawned with `maintenance_multiplier = 1` cost their owner 15.4 gold a month (about 0.3 a galley), and the default spawn cost nothing. A quarter of Venice's 98 galleys would cost the borrower about 7.5 gold a month; Venice itself gained about 12.7 a month in that probe.
- **Hire fee:** a monthly payment to the lender, small for war partners and larger for charters. Or the whole term's fee up front, a month or two cheaper.
- The first month is paid on signing. One missed payment warns both rulers; a second sends the ships home.
- Fee levels and term lengths: proposed in the PR that builds step 1, from the costs above.

### The contract

- **The monthly check:** a monthly event on the borrower carries the lender and the lender's main title as event targets. Each month it renews "Ships away" on the lender's current ports, takes the fee, and checks whether the contract ends. Renewing means removing the modifier and adding it again: adding one a province already has keeps the first one's expiry (a probe added it for 100 days, then 200, and the save kept the 100).
- **Reloads:** modifiers with their expiry dates, flags, earmarks and delayed events with their targets are all kept in the save. A probe saved, reloaded, and its delayed event fired on its day with both its character and title targets.
- **Ports and shipyards change:** a new shipyard is cut by the percentage from the day it is built, and a new port at the next check. A lost port's modifier is removed at the check, or lapses after its 45 days; the game removed an expired modifier between 14 and 42 days after its date.
- **A ruler dies:** after the lender's death or a new doge, the contract stays with the main title, and the new holder may honour it or recall the ships. After the borrower's death, its heir keeps the fleet and the contract to the term. A fleet that disbands with troops aboard may lose them [Unverified].
- **It ends** at the term, at peace for a war loan, on recall, after a second missed payment, or if the two go to war with each other. Then the fleet is disbanded (`disband_event_forces`) and "Ships away" is removed.
- **If the monthly event ever stopped,** "Ships away" would lapse by itself, a few weeks after its 45 days. The in-game tests check the chain on every run.

### Later

- Step 2: charters (assembly time, the lender's port, sailing season).
- After the first stable release: AI rulers borrow and lend like players (#52).

## Files

- The prototype's files: `decisions/afl_decisions.txt`, `events/afl_events.txt`, `common/scripted_triggers/afl_triggers.txt`, `common/scripted_effects/afl_effects.txt`, `localisation/afl_localisation.csv`. v0.1 keeps this layout. Conditions go in scripted triggers and each step in a scripted effect, so the in-game tests in `tests/game/allied_fleets/` run the same code players do (#38).
- No vanilla file is overridden.

## Log lines

Each step writes an `afl:` line to `game.log`, for example `afl: request from <requester> (<id>) to <ally> (<id>)`. [Unverified] They appear only when the game runs with `-debugscripts` or `-scriptlog` (per `vanilla/ChangeLog.txt`), so normal play shows nothing. To include them in a bug report, add `-scriptlog` to the game's Steam launch options and send `Documents/Paradox Interactive/Crusader Kings II/logs/game.log`.

## Save compatibility

v0.1 adds decisions, events, localisation, modifiers, flags and earmarks, and removes the prototype's. The prototype was never released, so no player save holds its state. [Inference] A save made with v0.1 should load without it, leaving at most stray flags, timed modifiers that lapse, and earmarked fleets. Not yet tested.

## Multiplayer

Every player needs the same version, because the checksum changes. Both players see the terms, a note when the ships arrive, a warning before the term ends, and a note when they go home.
