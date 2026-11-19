# Ověření uložených jmen a plán jejich rozdělení

Aktuální čtecí snímek projektové instance obsahuje 25 951 dokumentů v `firesport.results`. Opravný skript a backend přistupují z různých síťových prostředí ke stejnému procesu MongoDB, ověřeno shodným identifikátorem z příkazu `hello`. Administrační frontend posílá dotazy `/v1/` stejnému backendu. Připojovací údaje nejsou součástí reportu.

| Metrika u auditovaných 154 výsledků | Počet |
| --- | ---: |
| Uložený `source_full_name` | 154 |
| Vyplněná obě oddělená jmenná pole nyní | 0 |
| Doložená rozdělení z předchozího auditu | 22 |
| Nově doložená rozdělení | 24 |
| Navrhované aktualizace | 46 |
| Zatím nejednoznačné | 108 |

## Dva aktuální dokumenty

| Pole | Svinov | Albrechtice Zámostí |
| --- | --- | --- |
| `_id` typu ObjectId | `0c6d0ddd3062d24382ad4e58` | `055420e5e306b28fb7d374e2` |
| `source_full_name` | `Souček  Stanislav Gabriel` | `Popalová Monika Nora` |
| `imported_athlete.first_name` | `""` | `""` |
| `imported_athlete.last_name` | `""` | `""` |
| `imported_athlete.birth_year` | `2010` | `2011` |
| `imported_athlete.fscode` | `null` | `null` |
| `team` | `Svinov` | `Albrechtice Zámostí` |
| `final_time` | `21.49` | `20.34` |
| `rank` | `10` | `10` |

Text původního jména a `source_name_evidence` jsou na nejvyšší úrovni dokumentu. Oddělená jména jsou v objektu `imported_athlete`. Oba dokumenty jsou bez vazby na profil. Čtecí kontrola skutečné administrační trasy v běžícím backendu vrátila pro obě ID přesné hodnoty výše a odvozený stav `needs_review` s důvodem `name_segmentation_review`. Veřejné `GET /v1/results/{id}` pro ně správně vrací 404 podle současného filtru nepřiřazených výsledků.

## Doklady a povolená pole

Původních 22 návrhů vychází z [předchozího auditu](athlete-source-name-segmentation-audit.cs.md). Dalších 24 návrhů se podařilo doložit pro dvě jména. U **Jan Kurt Bareš** porovnání zprávy pořadatele s opačným pořadím v původní listině a se shodným ročníkem a sborem určuje hranici po slovu Kurt u 13 výsledků. U **Sofie Edita Chvojková** zachycuje nezávislá listina oddělené sloupce a shodný ročník i sbor u 11 výsledků. Pouhá konvence pořadí slov u dalších víceslovných zápisů hranici mezi poli nedokládala. [Zpráva pořadatele STIMAX CUP](https://mladez.dh.cz/images/Dokumenty/mladez/souteze/2023/2023_-_clanek_STIMAX_CUP_2023_-_4_kolo_Chomutov_-_30_9__celkove_vysledky.pdf) · [Samostatné sloupce v listině z Prahy](https://stovky.cz/sedesatky/praha/2024/starsi_divky.pdf)

Každá navržená operace je omezena na `imported_athlete.first_name`, `imported_athlete.last_name` a `source_name_evidence.segmentation`. Původní text, původní zdrojový lokátor a stav párování zůstávají. Plán zachovává časy, pořadí, soutěže, disciplíny, kategorie a odkazy na profily. Nástroj při neshodě původního řádku, lokátoru, jména, ročníku nebo týmu dotčenou opravu nevytvoří. Pomocná zápisová funkce kontroluje úplný dokument před podmíněnou aktualizací. Příkazový nástroj umí pouze lokální dry-run.

```bash
python -m scripts.prepare_structured_name_repair --dry-run \
  --snapshot "$SNAPSHOT" --audit "$ORIGINAL_AUDIT" \
  --supplemental "$SUPPLEMENTAL_EVIDENCE" --report "$REPORT"
```

Nácvik provedl všech 46 aktualizací na kopii 154 výsledků v samostatné MongoDB. Porovnání našlo přesně očekávané změny a následný dry-run navrhl nula aktualizací. Integrační test navíc zapisuje do skutečné izolované MongoDB a čte strukturovaná pole přes HTTP administrační trasy v testovací FastAPI aplikaci. Před případným schváleným zápisem znovu načíst plánovaná ID a pořídit zálohu jejich předchozích hodnot. Projektové databáze se tento krok pouze četl.
