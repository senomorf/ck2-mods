# CK2 notes

Facts about CK2 script and behaviour that someone has confirmed. One line each, with the source. Unconfirmed ideas don't go here.

| Fact | Source | Confirmed |
| --- | --- | --- |
| EMF forces LF line endings for `.txt`, `.csv`, `.lua`, `.gui`, `.gfx` | [EMF .gitattributes](https://github.com/EMFTeam/EMF/blob/master/.gitattributes) | read 2026-11-11 |
| Localisation CSV header is `#CODE;ENGLISH;FRENCH;GERMAN;;SPANISH;;;;;;;;;x`; lines end `;x` | [EMF localisation](https://github.com/EMFTeam/EMF/tree/master/EMF/localisation) | read 2026-11-11 |
| `spawn_fleet` takes `owner`, `province`, `earmark`, `disband_on_peace`, `troops = { galleys = { N N } }` | [EMF unit_decisions.txt](https://github.com/EMFTeam/EMF/blob/master/EMF/decisions/unit_decisions.txt), `conscript_merchant_ships` | read 2026-11-11, not tested in game |
