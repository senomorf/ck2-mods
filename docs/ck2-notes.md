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
