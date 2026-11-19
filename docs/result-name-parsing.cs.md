# Jména závodníků ve výsledcích

Datový model používá `imported_athlete.first_name` a `imported_athlete.last_name`. Každá hodnota může obsahovat více slov. Extrakce ukládá původní text `source_full_name` a rozdělené hodnoty používá samostatně. U staršího vstupu tvořeného jen oddělenými poli ukládá import i jejich původní obsah v existujícím `source_person_name`.

Hranici jména dokládají oddělené sloupce, jednoznačný oddělovač nebo pravidlo doložené pro konkrétní formát listiny, například výslovně označené příjmení verzálkami. Doložené pořadí pomáhá u dvou jmenných částí. U víceslovného zápisu bez doložené hranice zůstávají nerozlišené položky prázdné a ukládá se původní text. Výsledek s chybějícím jménem nebo příjmením jde ke kontrole. Při párování musí být shoda úplná v obou polích. Částečný zápis může upozornit na možného kandidáta.

## Audit uložených výsledků

Ze složky `backend/` se spustí nad čtecím snímkem MongoDB. Adresář zdrojů obsahuje uložený soubor `source.html` v podsložce `source_id(url)` pro každou listinu. Doplňující doklady mohou potvrdit hranici v dalším vydání veřejné listiny se shodným zněním, ročníkem a sborem. Případ bez sboru může využít shodný odkaz na účastníka na stránkách téhož pořadatele, pokud je sbor doložen v jiné jeho listině. Odkaz na účastníka se používá pouze pro ověření jmenných polí.

```bash
python -m scripts.audit_result_names --snapshot "$SNAPSHOT" --sources "$SOURCES" \
  --supporting "$SUPPORTING_EVIDENCE" --report "$REPORT"
```

Report obsahuje otisk plánu, přesné lokátory, původní hodnoty a operace pro budoucí schválený zápis. Skript pracuje s lokálními soubory a nemá režim zápisu do MongoDB. Po schválení konkrétního otisku se ověří obnovitelná záloha a aktuální otisky jednotlivých dokumentů. Podmíněný zápis musí povolit jen pole z reportu. Po zkoušce na izolované kopii se ověří úplný rozdíl dokumentů a zopakuje audit. Předchozí vazba na profil a již uložený `source_full_name` mají zůstat zachované. Ověření hranice jména samo o sobě nikoho nepřiřazuje k profilu.
