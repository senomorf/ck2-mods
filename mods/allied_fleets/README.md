# Allied Fleets

Lets a ruler borrow galleys from another ruler: for crusades and other wars overseas, and above all for landlocked players in multiplayer. CK2 lets an army board only its own ruler's ships (engine behaviour, per player reports in #8), so the borrower gets a fleet of its own, and the lender's own holdings raise as many fewer galleys while it is away.

**Status:** this is the design for v0.1, agreed with the owner on 2026-11-14 and 2026-11-15 (issue #8; discussion and sources in the design doc linked there). Step 1, the war loan, step 2, charters, and step 3, galley companies, are built. Nothing below has been tested in game by a player; the campaign test's in-game tests run each step on AI rulers. v0.2 (AI rulers using the mod, #52; owner's choice of design, 2026-11-15) is built in steps on branches that stay unmerged until `allied_fleets-v0.1.0` is tagged; step 1, the lender's score, is below.

## How it worked in reality

Rulers who needed ships hired them, with their crews, by contract. The contract set the men and horses to carry, a price, a term, a port and a date. Venice's 1201 contract for the Fourth Crusade carried 33,500 men for one year at four marks per horse and two per man, and Venice added fifty galleys of its own for half the conquests (Villehardouin). Allies in the same war sailed with the army; everyone else bought passage. The design doc lists the sources.

## Design

Option C of the design doc: one contract, with war-loan terms for allies and war partners, and charter terms for anyone else.

### Who may lend and borrow

- **Borrower:** any playable ruler. No port is needed: armies board ships at sea from any coast.
- **Lender:** a ruler with a holding of its own whose buildings give galleys (a shipyard, an arsenal, a nomad harbour, or a family palace). It lends from its own holdings only (owner's choice, 2026-11-15): its vassals' ships are theirs, and serve their liege, not the liege's ally.
- **War loan (step 1):** the two are allied, or on the same side of a war (crusade partners are temporary war allies, whom `is_allied_with` misses).
- **Charter (step 2):** anyone not at war with the lender. A player asks for one, or a player with ships offers one to another player (owner, 2026-11-14).
- **Galley company (step 3):** a player with ships founds a mercenary company of its galleys, which anyone the game lets hire mercenaries may hire (owner, 2026-11-15).
- One contract per ruler at a time, as borrower or as lender (a galley company counts as one). Nobody lends and borrows at once, so two allies can't trade fleets to avoid paying for their own. A lender considers one request at a time, so two askers can't overwrite each other's terms.
- No lending while the lender's own fleet is raised, so the same ships can't serve twice. This needs a trigger that sees a raised fleet: in probes neither `any_army` nor `has_raised_levies` saw a spawned fleet, and whether `has_raised_levies` sees a raised one is still to test. If nothing does, this rule goes.

### What is lent

- **A number of galleys:** 50, 100, 150, 200, 300, 400 or 500 (owner, 2026-11-14 and 2026-11-15: multiples of 50, since armies in play run from about 5,000 men to 50,000 and more, and a galley carries 100, `NUMBER_OF_TROOPS_PER_GALLEY` in `vanilla/common/defines.lua`). The borrower picks the count in an event of three pages: 50 or 100 (afl.10), 150 or 200 (afl.14), 300, 400 or 500 (afl.15), each page with "more galleys" and "never mind", since an event window has four option slots (`vanilla/interface/eventwindow.gui`; a box UI probe showed four of eight options at 1280x720 and 1920x1080). Only the counts the lender's own holdings hold are offered, each with its men and its monthly cost. Its fleet is spawned with exactly that many (`troops = { galleys = { N N } }`).
- **What the lender holds:** the galleys its own holdings' buildings give before bonuses, counted in script: each building's `galleys` (every level counts: `ct_shipyard_1` 7, `ct_shipyard_2` 8, an arsenal 15 a level, and so on, `vanilla/common/buildings/`), and 25 for a family palace (`vanilla/common/static_modifiers.txt`). On the test box this gave the Doge of Venice 73 in 1067 (Venezia 30, the Contarini palace 43), which the game raises as about 88 (box probe 6, `docs/ck2-notes.md`). The game adds percentage bonuses to that base, so a lender keeps at least those while its ships are away.
- **Where it appears:** a war loan appears at once, near the borrower; a charter, on signing, at the lender's port.
- **Ships away:** each of the lender's own holdings with ships carries the same percentage cut, so together they lose the count lent: 100 x count / base, rounded up, so up to 1% of the base more. The cut is stacked copies of two holding modifiers, −10% and −1% `galleys_perc`, at most 19 on a holding. A percentage takes that share of the holding's base whatever its other bonuses (in probe 6, ten −1% copies took Venezia from 36 galleys to 33). Earlier probes ruled out the alternatives: a flat `galleys = -10` took 10 off each holding and emptied the small ones, `galleys_max_levy` is not a modifier the game accepts, and no script can read a fleet's size.
- **Vassals keep their ships.** Their holdings carry no cut, so they have nothing to mind.
- **The lent fleet keeps its size.** If the lender loses holdings, its remaining ones take the cut, up to 100% of their base, and the borrower keeps the count it was lent.

### Payment

- **Crew wages:** the fleet's upkeep, charged by the game to the borrower as for its own ships (`spawn_fleet` with `maintenance_multiplier = 1`). Galley upkeep is a fixed rate, `GALLEYS_MAINTENANCE = 300` in `vanilla/common/defines.lua`; in a probe, 50 galleys cost their owner 15.4 gold a month (about 0.3 a galley), and a fleet spawned without the multiplier cost nothing. Seafarer religions pay less (`LOOTER_SHIP_MAINT_MULT = 0.1`).
- **The lender's margin:** each month the borrower also pays the lender a tenth of the usual wages, 0.03 gold a galley (owner, 2026-11-14: "a percentage over ship wages", 10% chosen; 2026-11-15: the margin goes to the lender). That is 1.5 gold a month for 50 galleys and 15 for 500.
- **Unpaid crews:** a borrower in debt at the monthly check pays no margin and leaves the wages unpaid; the first month warns both rulers, and a second in a row sends the ships home.
- A war loan runs until peace and has no payment up front; a charter has both (below).

### The contract

- **The monthly check:** a monthly event on the borrower carries the lender and the lender's main title as event targets. Each month it checks whether the contract ends, takes the margin, counts the lender's holdings again and renews "Ships away" on them for 45 days. Renewing means removing every copy (`remove_holding_modifier` removes them all, probe 6) and adding them again.
- **Reloads:** modifiers with their expiry dates, flags, earmarks and delayed events with their targets are all kept in the save. A probe saved, reloaded, and its delayed event fired on its day with both its character and title targets.
- **Holdings and shipyards change:** a new shipyard on a holding with ships is cut by the percentage from the day it is built, and the next check counts it in the base, so the cut shrinks. A new holding with ships is cut from the next check. A holding the lender loses keeps its copies until they lapse after their 45 days; the game removed an expired province modifier between 14 and 42 days after its date, and holding modifiers are not yet observed.
- **A ruler dies:** after the lender's death or a new doge, the contract stays with the main title: the monthly check finds the title's holder, who is told of the loan and may recall the ships. The cut moves to the new holder's holdings, and the old holder's, if still landed, are cleared. The borrower's death ends a war loan or a charter (on_death, before succession); an heir keeping the fleet to the term is for later. A fleet that disbands with troops aboard may lose them [Unverified].
- **It ends** at the term, at peace for a war loan, on recall of a war loan, after a second missed payment, or if the two go to war with each other. A recall takes effect at the next monthly check, so the ships leave within the month. Then the fleet is disbanded (`disband_event_forces`) and "Ships away" is removed from the lender's holdings. At peace the game disbands the fleet itself (`disband_on_peace`), and the next check ends the contract.
- **If the monthly event ever stopped,** "Ships away" would lapse by itself, a few weeks after its 45 days. The in-game tests check the chain on every run.

### Charters (step 2)

- **Asking:** Hire Ships, in the lender's diplomacy menu, for a player in no other contract, of a ruler with ships of its own who is not at war with them. The asker picks the count on three pages as for a war loan (afl.40, afl.41, afl.42); only the counts the lender's own holdings hold and the asker can pay on signing are offered. The lender signs or refuses (afl.43).
- **Offering:** Offer Ships for Hire, in another player's diplomacy menu, for a ruler with ships of its own (owner, 2026-11-14: "I offer contract for 50, 100, 150 ships etc."). The lender picks the count (afl.50, afl.51, afl.52), and the player signs or declines (afl.53). Players only: AI rulers don't hire ships yet (#52).
- **Price** (owner, 2026-11-15): the crews' wages through the game's upkeep, as for a war loan; a margin of a quarter of the wages to the lender each month, 0.075 gold a galley; and two months' wages on signing, 0.6 gold a galley, which the lender keeps however the charter ends. For 50 galleys: 30 gold on signing, then about 15 in wages and 3.75 to the lender a month.
- **Where the ships wait:** at the lender's port, its capital if that has one, else one of its own holdings with ships (`capital_scope = { port = yes }`; holding: `location`). The fleet appears there on signing, under the borrower's command, whatever the count or the season (owner, 2026-11-15: "At once, in the lender's port"), and "Ships away" goes on the lender's holdings. The borrower's army marches to the port to board, or the fleet sails to the army.
- **Term:** a year from signing, counted by the monthly check: twelve checks, each taking the margin; the eleventh warns both rulers (afl.46). Peace doesn't end it, and the lender can't recall the ships: the fleet is spawned without `disband_on_peace`, and Recall Our Ships is for war loans only.
- **It ends early** if the two go to war with each other, after a second unpaid month, at the borrower's death, or if the fleet is gone. After the lender's death the title's new holder takes the contract over, as for a war loan.

### Galley companies (step 3)

- **Why** (owner, 2026-11-15: "We could also use mercenary contracts for this. There are already in-game features to assemble mercenary company. We could also offer fleets like that"): a ruler whose ships stand idle hires them out to whoever pays, without choosing a borrower. The game's own mercenary companies do the hiring, the fleet and the upkeep, so the mod adds only the founding and the end.
- **Founding:** Found a Galley Company, a decision for a player in no other contract, with ships in its own holdings and no company yet. It picks 50 to 500 galleys on three pages (afl.60, afl.61, afl.62), as many as its own holdings hold. The company is a landless mercenary title with a new captain of the founder's culture and religion (`create_title` with `mercenary = yes` and `army_template`, as in `vanilla/decisions/ze_decisions.txt`), sized to the count chosen with `change_mercenary_composition`. It works without DLC in probes, though vanilla gates its own companies behind one. "Ships away" goes on the founder's holdings at once, and a monthly check (afl.65) renews it while the company exists.
- **Price:** the game's own, as for any company it makes; in probes a hirer paid 1 gold a galley on hiring, which went to the captain, then 0.9 a galley a month: 50 and 45 gold for 50 galleys. The founder gets a share of the company's pay (`siphons_income_to_creator = 0.25`); one probe paid 6.6 gold of a 45-gold month, which is not explained yet, so the texts say "a share".
- **Who hires it:** anyone the game lets hire it from the Mercenaries list (F6), the founder's enemies included: in probes a ruler kept the company when its founder declared war on him, and hired it again during the war. No effect dismisses a company or refuses a hire, and a created title has no `allow` block, so the mod can't stop it.
- **Where the fleet appears:** off the hirer's capital if it is coastal; for a hirer without a port, at the company's base (probes: King Harold's off Dover; Bohemia's in the Sound by Sjælland, though the tooltip said "nearby Prag").
- **Its home port** (owner's choice, 2026-11-15, "Build it with the home-port pin"): each hire moves the company's base to the hirer's capital, so AI hirers in observe mode carried a Danish company to Béjaïa and then Fès within nine months. When a hirer dismisses it (`on_mercenary_dismissed`, afl.66), the mod sets its base back to the founder's port (`set_preferred_capital`, which a probe confirmed).
- **Its end:** Disband Our Galley Company, only while nobody has hired it, since destroying a hired company left its hirer a fleet that named a missing title in a probe. The founder's death ends it too (afl.68): at once if idle, otherwise the day after its hirer dismisses it (afl.69). "Ships away" is removed, and the founder is told (afl.67). A founder who loses all its land loses the company at the next monthly check.
- **Limits:** one company per player; while it exists the founder can't lend or hire ships. AI rulers don't found companies (#52). [Unverified] How often AI rulers hire one, and what the founder earns in a year, are for the owner's round.

### The lender's score (v0.2, step 1)

- **Why:** in v0.1 an AI lender agrees three times in four, whatever is asked. In the cases the design doc for v0.2 found, maritime powers hired out their fleets for pay (Genoa to Castile in 1147, to France in 1190, 1246 and 1340), and lenders refused for reasons beyond gold: the Almohad caliph probably turned down Saladin's request for ships around 1190 (disputed). A borrower's credit mattered too: the Fourth Crusade's leaders owed Venice 85,000 silver marks, "could only initially pay 35,000", collected 14,000 more under threat, and paid the rest by attacking Zara for Venice (Wikipedia, "Fourth Crusade", read 2026-11-15).
- **How:** one score, built from the reasons below. An AI lender answers a war loan request (afl.11) or a charter request (afl.43) by it: 20 or more always agrees, 10 to 19 two times in three, 1 to 9 one in three, 0 or less never. A player sees the same score on Ask for Ships and Hire Ships before asking, as the game shows its own diplomacy: "yes", "maybe" or "no" with each reason and its value (`ai_acceptance`, `vanilla/decisions/00_decisions.info`). A "no" greys out the decision. A player lender gets +100, so the decision stays open to them, and answers for themselves as before.
- **The reasons** (Root = the lender, From = the ruler asking; `common/scripted_triggers/afl_score_triggers.txt`):

| Reason | Value |
|---|---|
| Base: war loan / charter | -5 / 10 |
| A merchant republic (charters only) | +15 |
| Opinion of the asker 50 or more / 25 to 49 | +25 / +10 |
| Opinion -25 to -49 / -50 or less | -15 / -40 |
| Allied with the asker | +15 |
| In the asker's realm | +10 |
| On the asker's side of a war | +10 |
| At war in a war without the asker on its side | -20 |
| Has a fleet raised: its galleys are at sea | -20 |
| Of another religion group | -40 |
| The asker is pledged to or fights a crusade of the lender's religion | +15 |
| The asker is at war with the lender's ally | -50 |
| The lender is in debt and wants the pay | +10 |
| The asker is in debt | -20 |
| The lender is a player | +100 |

- [Inference] The base of -5 for a war loan follows the design doc's finding: no case was found of a king lending his own fleet to an ally, so an AI ally lends readily only when it likes the asker or shares its war. No source was found for the faith reason (a Church ban on selling galleys to Muslims was looked for and not confirmed); it rests on every case found being between rulers of one faith, or of Rome and Byzantium.
- **One list, written twice:** the game can't compute an `ai_acceptance` from an effect, so the reasons are in the decisions (what a player sees) and in `common/scripted_effects/afl_score_effects.txt` (what the AI answers by). `tests/test_afl_score.py` fails if the two differ, and a decision taken logs `score shown differs` if the score it showed is not the one computed (box probe 20 found the shown score readable as `local_ai_acceptance_score`).
- **Unchanged:** a player's own answers, the counts, the prices and the contracts. AI rulers still don't ask for ships (step 2).

### Later

- A borrower's heir keeping the ships to the end of the term.
- After the first stable release: AI rulers borrow and lend like players (#52).

## Files

- `decisions/afl_decisions.txt`: Ask for Ships (`afl_ask_war_loan`), Hire Ships (`afl_hire_ships`) and Offer Ships for Hire (`afl_offer_ships`), all in the other ruler's diplomacy menu, and Recall Our Ships (`afl_recall_ships`); Found a Galley Company (`afl_found_company`) and Disband Our Galley Company (`afl_dissolve_company`), in the decisions list.
- `events/afl_events.txt`: the choice of count (afl.10, afl.14, afl.15), the lender's answer (afl.11), notices (afl.12, afl.13, afl.21, afl.23, afl.24), the monthly check (afl.20) and the borrower's death (afl.30); for charters, the asker's count (afl.40, afl.41, afl.42), the lender's answer (afl.43), the lender's count for an offer (afl.50, afl.51, afl.52), the answer to it (afl.53) and notices (afl.44, afl.46, afl.54); for galley companies, the founder's count (afl.60, afl.61, afl.62), notices (afl.63, afl.67), the monthly check (afl.65), a dismissal (afl.66), the founder's death (afl.68) and the end after a dismissal (afl.69).
- `common/scripted_triggers/afl_triggers.txt` and `common/scripted_effects/afl_effects.txt`: every condition and step, so the in-game tests in `tests/game/allied_fleets/` run the same code players do (#38). The lender's score (v0.2): `common/scripted_triggers/afl_score_triggers.txt`, `common/scripted_effects/afl_score_effects.txt` and `localisation/afl_score.csv`.
- `common/event_modifiers/afl_modifiers.txt` ("Ships away", two holding modifiers), `common/on_actions/afl_on_actions.txt` (on_death, on_mercenary_dismissed), `localisation/afl_localisation.csv`.
- No vanilla file is overridden.

## Log lines

Each step writes an `afl:` line to `game.log`: `request from ... to ..., who can spare N`, `request withdrawn by`, `refused by`, `war loan of N galleys from ... to ...`, `margin of M paid by ... to ...`, `wages unpaid by`, `... passed from ... to ...; the loan goes on`, `recalls the ships`, `borrower ... died`, `war loan ended`; for charters, `charter request from`, `charter offer from`, `charter offer withdrawn by`, `charter offer declined by`, `charter of N galleys from ... to ...: L paid on signing`, `charter fleet of N galleys ready in P`, `charter's term over after 12 months`, `charter ended`; for galley companies, `company of N galleys founded by ...: NAME, captain ...`, `company not founded by`, `NAME based at P`, `NAME serves HIRER`, `NAME dismissed by HIRER`, `founder ... died`, `... has no company any more`, `NAME dissolved`, `NAME dissolves when its hirer dismisses it`; for the lender's score (v0.2), `war loan score N by ... for ...`, `charter score N by ... for ...`, and `score shown differs from the score computed by D`. [Unverified] They appear only when the game runs with `-debugscripts` or `-scriptlog` (per `vanilla/ChangeLog.txt`), so normal play shows nothing. To include them in a bug report, add `-scriptlog` to the game's Steam launch options and send `Documents/Paradox Interactive/Crusader Kings II/logs/game.log`.

## Save compatibility

v0.1 adds decisions, events, localisation, modifiers, flags, earmarks and, with galley companies, created mercenary titles (`d_dyn_N` in the save, flag `afl_company`), and removes the prototype's (decision `afl_request_ships`, events `afl.1`, `afl.2` and `afl.3`, earmark `afl_lent_ships`, event targets `afl_requester` and `afl_ally`). The prototype was never released, so no player save holds its state. [Inference] A save made with v0.1 should load without it, leaving at most stray flags, timed modifiers that lapse, and earmarked fleets. Not yet tested. v0.2's lender score adds the variables `afl_score` (on the lender and on the ruler asking) and `afl_shown` (on the lender) and removes nothing.

## Multiplayer

Every player needs the same version, because the checksum changes. Both players see the terms, a note when the ships arrive, a warning after a missed payment, and a note when they go home. Only multiplayer shows Offer Ships for Hire, since it is offered to players only, and a player hiring another player's galley company. With v0.2's lender score, a player asking another player sees "maybe" with the reasons (`show_maybe_for_human`), [Unverified] never "no", since a player lender adds 100.
