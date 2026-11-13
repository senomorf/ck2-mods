# CK2 notes

Facts about CK2 script and behaviour that someone has confirmed. One line each, with the source. Unconfirmed ideas don't go here.

| Fact | Source | Confirmed |
| --- | --- | --- |
| EMF forces LF line endings for `.txt`, `.csv`, `.lua`, `.gui`, `.gfx` | [EMF .gitattributes](https://github.com/EMFTeam/EMF/blob/master/.gitattributes) | read 2026-11-11 |
| Localisation CSV header is `#CODE;ENGLISH;FRENCH;GERMAN;;SPANISH;;;;;;;;;x`; lines end `;x` | [EMF localisation](https://github.com/EMFTeam/EMF/tree/master/EMF/localisation) | read 2026-11-11 |
| `spawn_fleet` takes `owner`, `province`, `earmark`, `disband_on_peace`, `troops = { galleys = { N N } }` | [EMF unit_decisions.txt](https://github.com/EMFTeam/EMF/blob/master/EMF/decisions/unit_decisions.txt), `conscript_merchant_ships` | read 2026-11-11, not tested in game |
| Localisation files are Windows-1252/ISO-8859-1, not UTF-8 (71 of 96 EMF CSVs detect as iso-8859-1, 5 as ASCII) | `file -bi reference/emf/EMF/localisation/*.csv` | checked 2026-11-11 |
| `spawn_fleet` works without `earmark`, and accepts `province = closest` | `vanilla/decisions/jd_decisions.txt`, `vanilla/decisions/unit_decisions.txt` (3.3.3) | read 2026-11-12, not tested in game |
| CWTools CLI 0.6.0-alpha with the 2019 rules reports ~28,000 errors on vanilla 3.3.3, so its findings are hints, not facts | `cwtools ... --scope all validate errors` on `vanilla/` | checked 2026-11-12 |
| Targeted decisions live in a top-level `targeted_decisions = { }` block | e.g. `reference/emf/EMF/decisions/mnm_society_decisions.txt` | read 2026-11-11 |
| Linux 3.3.5.1 logs `After first history execution` to `game.log` once a boot reaches the main menu | `tools/smoke.sh` header; measured on the fleet runner | reported in #10; seen in the [smoke job](https://github.com/senomorf/ck2-mods/actions/runs/43420436244/job/131868779709) 2026-11-13 |
| An empty user folder stops at a "Choose language" dialog; `settings.txt` `gui = { language=l_english has_set_language=yes }` skips it, `language="l_english"` alone does not | same | reported in #10, 2026-11-13 |
| The Linux build without a Steam client logs `SteamAPI_Init() failed` and carries on only with no network; with one it asks to be started through Steam and exits 1 | same | reported in #10, 2026-11-13 |
| `system.log` names `mod/<folder>` when the game loads that mod | `tools/smoke.sh` header; measured on the fleet runner | reported in #10; seen in the [smoke job](https://github.com/senomorf/ck2-mods/actions/runs/43420436244/job/131868779709) 2026-11-13 |
| An unknown effect in an event logs `Unknown effect-type: "<name>" at  file: events/<file> line: <n>` to `error.log` at boot (two spaces before `file:`) | [smoke job on #12](https://github.com/senomorf/ck2-mods/actions/runs/43420596435/job/131869314332), CK2 3.3.5.1 Linux | checked 2026-11-13 |
