# 2026/27 League Membership

Snapshot date: 2026-09-12. Scope is the 12 competitions in `config/scope.json`.

| League | Country | Level | Expected | Actual | Status |
|---|---|---:|---:|---:|---|
| ENG1 | England | 1 | 20 | 20 | CONFIRMED |
| ITA1 | Italy | 1 | 20 | 20 | CONFIRMED |
| ESP1 | Spain | 1 | 20 | 20 | CONFIRMED |
| GER1 | Germany | 1 | 18 | 18 | CONFIRMED |
| FRA1 | France | 1 | 18 | 18 | CONFIRMED |
| POR1 | Portugal | 1 | 18 | 18 | CONFIRMED |
| NED1 | Netherlands | 1 | 18 | 18 | CONFIRMED |
| BEL1 | Belgium | 1 | 18 | 18 | CONFIRMED |
| TUR1 | Türkiye | 1 | 18 | 18 | CONFIRMED |
| CZE1 | Czechia | 1 | 16 | 16 | CONFIRMED |
| GER2 | Germany | 2 | 18 | 18 | CONFIRMED |
| GER3 | Germany | 3 | 20 | 20 | CONFIRMED |

Total rows: 222. Native membership validation: **PASS, 12/12 leagues**, independently reread from `native10-data-draft-20260913-04` on 2026-09-13. Expected counts, exact club/team sets and unique domestic league assignments all pass. Every required club is present and every excluded club is absent. Unknown baseline FIFA team IDs remain 0; no EA IDs were invented.

Belgium 18/15 and the German GER3/regional dependency chain are applied through typed native structures. Bayern 19 uses the documented stable modeled format; an exact transient 2027/28 size adjustment is not claimed. Unrelated lower-division squads remain outside scope.

This proves current league membership, not full squad completion, full semantic-diff completion or game runtime. Full data release remains blocked separately. Machine evidence: `league-membership-validation.json` and candidate `membership-validation.json`.

## Sources

- **ENG1** — [official 2026/27 source](https://www.premierleague.com/en/news/4675097/all-380-fixtures-for-202627-premier-league-season); SHA-256 `27455262c832f50308fd7fc027d942cd4027c6db94f8f77a03153b36cf097867`.
- **ITA1** — [official 2026/27 source](https://en.legaseriea.it/serie-a/news/looking-forward-to-the-2026-27-serie-a-fixture-list); SHA-256 `0395f45310e6fd7abde7558dd76ba589fd764ddb5be1df9d44e97a1a3b4e151a`.
- **ESP1** — [official 2026/27 source](https://www.laliga.com/laliga-easports/clubes); SHA-256 `7dc21d905da42305ef7100901e7bda02619b96c2e8826d91ed8b94979b7e7456`.
- **GER1** — [official 2026/27 source](https://www.bundesliga.com/de/bundesliga/clubs?firsttab=kader); SHA-256 `412ffdeb06c1d77fcf37c1f21e59412b59a0f519c7fa61732fffcb7d5fb5b8e5`.
- **FRA1** — [official 2026/27 source](https://ligue1.com/fr/articles/l1_article_5284-); SHA-256 `9405a33e7f9c2435db67bfbc806ca4eac7cd73463ba2032bc589f13d442f0685`.
- **POR1** — [official 2026/27 first-matchday media kits](https://www.ligaportugal.pt/news/28294/media-kits-1.a-jornada-liga-portugal-betclic); SHA-256 `61d16d815700a558bb7a99a47462ccd09b2ce17b92eb65eade6f52eba9359077`.
- **NED1** — [official 2026/27 source](https://eredivisie.nl/nieuws/definitief-programma-2026-27/); SHA-256 `5b02ea39f1324dcd660e19e3aa06b7dd12368b2f0ca7351f5f004214391bbbb7`.
- **BEL1** — [official 2026/27 source](https://www.proleague.be/jpl-clubs); SHA-256 `0a77b79bd718cfbbe545d18334177e3c460c15dd5a98a53a59430147320f25a1`.
- **TUR1** — [official 2026/27 source](https://www.tff.org/?pageID=198); SHA-256 `a0423b95de5880b4b95bf009b18d42f5fa5927b59f7bb735eca4ae265266fa2f`.
- **CZE1** — [official 2026/27 source](https://www.chanceliga.cz/Start); SHA-256 `dbad9f08f35c7ce79a4a69e97ba9d9ff48d817d45c65fe327512f7902067603a`.
- **GER2** — [official 2026/27 source](https://www.bundesliga.com/de/2bundesliga/clubs); SHA-256 `b4947004f58f5c89e12823d3842288cd274c7c9ab4faee8d750fa35ff077a966`.
- **GER3** — [official 2026/27 source](https://datencenter.dfb.de/competitions/4/seasons/current); SHA-256 `952520fbfcc60f1802def3ec1bf2248f8c565db74cf4e27d9ac47e73b969186c`.

## Promotion and relegation checks

The independent native audit compares every target competition against its authoritative 2026/27 set, including required entrants and excluded clubs. Earlier per-club movement-notice research is preserved in the machine report's superseded checkpoint. Current membership is established from authoritative current competition evidence, not historical marker inference.
