# Audit kvality jmen závodníků

Audit vychází z čtecího snímku projektové MongoDB a z dostupných zdrojových JSON v repozitáři. Pokrývá 4 438 profilů a 25 951 výsledkových dokumentů včetně archivních. Veškeré návrhy jsou lokální. Zápisová oprava databáze nebyla spuštěna.

## Tři případy z Ostravy

| Výsledková listina BO stovky, 3. října 2026 | MongoDB | Oficiální individuální čas | Příčina |
| --- | --- | --- | --- |
| Svinov, ročník 2010, střední dorostenci, 10. místo | Obě části jména jsou prázdné. Původní JSON obsahuje dvě hodnoty null. | 21,49 s, platný | HTML uvádí „Souček Stanislav Gabriel“. Extrakce nedoložila hranici jména a příjmení. Původní text je ve varování JSON. |
| Albrechtice Zámostí, ročník 2011, střední dorostenky, 10. místo | Obě části jména jsou prázdné. Původní JSON obsahuje dvě hodnoty null. | 20,34 s, platný | HTML uvádí „Popalová Monika Nora“. Extrakce nedoložila hranici jména a příjmení. Původní text je ve varování JSON. |
| Klimkovice, ročník 2012, mladší dorostenci, 8. místo | Uloženo `Petr juřina`. | 23,37 s, platný | Malé „j“ je už v HTML a v JSON. Import jej dosud ponechal i v hodnotě pro zobrazení. |

[Oficiální výsledková listina BO stovky](https://pozarnisporty.cz/races/988)

U všech tří řádků auditu odpovídá soutěž, skupina, klub, pořadí a výsledný čas. HTML je dostupné. Prázdná jména vznikla již při extrakci; import převáděl hodnoty null na prázdné řetězce a dříve jim bez kódu dával stav `unmatched`. Administrace spojila dvě prázdné hodnoty do prázdné buňky. Platné časy, kategorie a pořadí byly uloženy správně. Zobrazené pořadí slov ve zdroji nedokládá bezpečné rozdělení tříslovných jmen. Dokud nebudou k dispozici oddělená pole nebo potvrzení pořadatele, obě položky zůstávají k ruční kontrole.

## Výsledky úplného průchodu

| Metrika | Profily | Výsledky |
| --- | ---: | ---: |
| Prozkoumané dokumenty | 4 438 | 25 951 |
| Chybí jméno nebo příjmení | 0 | 154 |
| Chybí obě části | 0 | 154 |
| Platný individuální čas bez jména | — | 153 |
| Malé počáteční písmeno příjmení | 0 | 2 |
| Celé příjmení verzálkami | 0 | 135 |
| Celé křestní jméno verzálkami | 0 | 1 |
| Formátovací oprava bez zásahu do identity | 0 | 2 |
| Ke kontrole celkem | 1 | 323 |

Z 154 řádků s prázdnými jmény je 128 v aktivní individuální klasifikaci, 25 v historických skupinách a jeden ve stavu kontroly kategorie. Žádný z nich nemá odkaz na profil závodníka. Obě jednoznačné formátovací opravy patří dvěma různým výkonům Petra Juřiny. Verzálky jsou signál k ověření stylu zdroje. Audit dále našel 11 možných záměn polí a devět rozporů v diakritice vůči již připojenému profilu. Tyto rozpory nejsou důkazem správné varianty. Jeden profil má podezřelou interpunkci v křestním jménu. Počty jednotlivých příznaků se mohou překrývat.

Srovnání se zdrojovým JSON používá URL, původní kategorii, ročník, pořadí, klub a výsledný čas. Kontroluje pouze unikátní shody. V tomto pokrytí nebyl nalezen jednoznačný případ, kdy obě oddělená jmenná pole byla v JSON dostupná a v MongoDB některé chybělo. Starší výsledky bez dostupné zdrojové kopie nebo s jiným způsobem uložení tímto srovnáním pokryté nejsou.

## Oprava v aplikaci

- Názvy z extrakce zůstávají ve zdrojovém formátu. Nejednoznačné rozdělení dál zapisuje varování a neskládá identitu odhadem. Striktní JSON schéma se nemění.
- Import, matcher a modely pro zobrazení používají společnou normalizaci NFC, mezer a jednoduchého jednoslovného zápisu malými písmeny. Složená jména, částice, verzálky a smíšená kapitalizace se svévolně nepřepisují. Při změně se do nově importovaného výsledku uloží také původní hodnoty jmenných polí.
- Neúplné jméno se eviduje jako `needs_review` s důvodem `missing_name`. Platný čas a zdrojové údaje se uchovají. Import takový řádek automaticky nepřiřadí a bez ručního ověření vazby jej výpočet osobního rekordu vynechá. Jmenná normalizace nemění klíč stávajícího výsledku při opakovaném importu.
- Administrační fronta pro aktivní individuální výsledky odlišuje chybějící jméno od běžného nepropojeného výsledku. Nabízí filtr, české stavy a přístup k importovaným hodnotám a dostupnému zdroji. Celodatabázová kontrola včetně profilů, archivů, historických skupin a již spárovaných výsledků je v lokálním reportu.

## Bezpečný postup pro uložená data

Ze složky backendu spustit lokální plán nad úplným snímkem. Výstupní cesta musí být nová.

```bash
python -m scripts.audit_person_names \
  --snapshot "$SNAPSHOT" --source-root ../data --report "$REPORT"
```

Po samostatném schválení lze na dvou navržených dokumentech změnit pouze jednoznačně normalizovaná jmenná pole. Před každým zápisem ověřit otisk úplného dokumentu, uchovat původní hodnotu v `source_person_name` a použít podmíněnou aktualizaci. Opakovaný audit má pro tyto dva řádky dát nula návrhů. U neúplných jmen lze odděleně schválit změnu příznaku na `needs_review`. Doplnění jména nebo vazby vyžaduje konkrétní zdrojový důkaz. Časy, pořadí, výsledkové dokumenty, kategorie, FSCode a stávající vazby mají zůstat zachované. Skript nyní podporuje výhradně dry-run.
