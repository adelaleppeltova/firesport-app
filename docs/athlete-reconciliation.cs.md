# Hromadné párování výsledků k závodníkům

`scripts.reconcile_athletes` načte úplný snímek databáze a projde všechny výsledky a profily. Zapisuje vazby a důvody kontroly u aktivních individuálních výsledků bez odkazu na závodníka. Uložené vazby prověří kvůli chybným referencím a rozporům v identitě. Katalog kategorií určuje, které výsledky se zobrazují v admin frontě.

- Jedinečný FSCode vyžaduje přesné jméno a ročník bez rozporu. Přesné jméno a doložený ročník mohou stačit při jediném kompatibilním profilu a konzistentních výsledcích.
- Jeden profil může mít více FSCode. Každý další kód musí být doložen shodným jménem a ročníkem a mít jediného vlastníka. Pro založení profilu musí být vyplněné jméno i příjmení. Osamocený výsledek s úplným jménem může získat profil bez ročníku, pokud kontrola nenajde další možné záznamy téže osoby.
- Odlišnosti v diakritice, podobný zápis s podpůrným údajem, nejednoznačný kód nebo vícenásobný výsledek ve stejné listině jsou důvodem k ruční kontrole. Při dřívějším ručním odpojení zůstává v platnosti rozhodnutí administrátora.
- Součástí reportu je inventura všech JSON v adresáři `data/`. Obsahuje odchylky od schématu, varování extrakce a řádky, u nichž se nepodařilo najít odpovídající výkon. Kontrola souborů používá původní uložený řádek a srovnání jména, ročníku, klubu, pořadí, startovního čísla a výkonu v odpovídající soutěži. Neshoda vyžaduje porovnání s listinou. Doplnění chybějících soutěží nebo oprav výsledků je samostatná operace dle [postupu extrakce](extraction.cs.md).

## Spuštění

Použijte úplný NDJSON snímek se záznamy `count` z migračního nástroje (`--dry-run --live-read-only --save-snapshot`). Report uložte pod novým názvem do soukromé diagnostiky mimo Git. Z adresáře `backend/` spusťte:

```bash
python -m scripts.reconcile_athletes --snapshot "$SNAPSHOT" --report "$REPORT"
```

Po kontrole reportu a ověření obnovitelné zálohy otestujte stejný zápis v izolované kopii. Pro zápis nastavte `FIRESPORT_RECONCILE_MONGO_URI` na schválenou instanci MongoDB, pozastavte souběžné importy a administrační zápisy a použijte otisk z reportu.

```bash
python -m scripts.reconcile_athletes --snapshot "$SNAPSHOT" \
  --apply "$REPORT" --approve-plan "$PLAN_SHA256" --database firesport
```

Skript přepočte plán a porovná úplný uložený obsah dotčených kolekcí se snímkem. Profily mají deterministická ID. Po přerušení lze stejným příkazem zopakovat stejný plán, pokud všechny již zapsané hodnoty odpovídají jeho výsledku. Po dokončení ověřte stav administrační fronty a spusťte druhý dry-run nad novým snímkem. Rozsah změn lze ověřit porovnáním obou snímků.
