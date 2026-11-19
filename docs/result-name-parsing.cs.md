# Jména závodníků ve výsledcích

Import zachovává přesný text `source_full_name` a každé přítomné oddělené pole ukládá beze změny do `source_person_name`. Chybějící klíč v původních polích se liší od hodnoty `null` nebo prázdného řetězce. `imported_athlete.first_name` a `imported_athlete.last_name` obsahují interpretované hodnoty. Každá může obsahovat více slov. Pokud je celé pole ve verzálkách, dostane každá část jména počáteční velké písmeno. Administrace ukazuje interpretovaná pole a původní hodnoty s vlastními popisky.

Hranici jména dokládají oddělené sloupce, jednoznačný oddělovač nebo pravidlo doložené pro konkrétní formát listiny, například výslovně označené příjmení verzálkami. Doložené pořadí pomáhá u dvou jmenných částí. U víceslovného zápisu bez doložené hranice zůstávají nerozlišené položky prázdné a ukládá se původní text. Výsledek s chybějícím jménem nebo příjmením jde ke kontrole. Při párování musí být shoda úplná v obou polích. Částečný zápis může upozornit na možného kandidáta.

## Audit uložených výsledků

Přepínač „Chybí jméno nebo příjmení“ v administraci používá stejnou podmínku jako audit. Za chybějící se považuje nepřítomná hodnota, `null`, prázdný řetězec, samotné bílé znaky nebo hodnota jiného typu než řetězec. Formátovací příznaky jsou samostatné. Porovnání vykazuje celou databázi i podmnožinu aktivních individuálních výsledků v administrační frontě.

Ze složky `backend/` se spustí nad čtecím snímkem MongoDB. Adresář zdrojů obsahuje uložený soubor `source.html` v podsložce `source_id(url)` pro každou listinu. Doplňující doklady mohou potvrdit hranici v dalším vydání veřejné listiny se shodným zněním, ročníkem a sborem. Případ bez sboru může využít shodný odkaz na účastníka na stránkách téhož pořadatele, pokud je sbor doložen v jiné jeho listině. Odkaz na účastníka se používá pouze pro ověření jmenných polí.

```bash
python -m scripts.audit_result_names --snapshot "$SNAPSHOT" --sources "$SOURCES" \
  --supporting "$SUPPORTING_EVIDENCE" --report "$REPORT"

python -m scripts.compare_result_name_audits --previous "$PREVIOUS_SNAPSHOT" \
  --snapshot "$SNAPSHOT" --source-root ../data --report "$COMPARISON"
```

Volitelný vstup `--verified-results` obsahuje vizuálně ověřené řádky původního PDF s číslem strany, startovním číslem, kategorií, otiskem PDF a otiskem uloženého zdrojového řádku. Při neshodě lokátoru se případ předá k ruční kontrole.

Dry-run pracuje s lokálními soubory. Každý návrh uvádí otisk dokumentu, přesný lokátor, důkaz, původní stav pole, navrženou hodnotu a důvod. Povolená jsou pouze chybějící pole `imported_athlete.first_name` a `imported_athlete.last_name`. Oba původní zdrojové záznamy, stav párování a vazba na profil jsou mimo rozsah plánu.

Ke schválení se předkládá konkrétní otisk plánu. Po schválení pořiďte obnovitelnou zálohu a načtěte dotčené dokumenty znovu. Při rozdílném otisku vytvořte nový návrh ke schválení. Zkoušku proveďte na kopii a porovnejte úplné dokumenty. Plánovaný zápis použije podmínku na původní stav dokumentu a povolí jen uvedená jmenná pole. Po zápisu ověřte počty změn, úplný rozdíl všech dotčených dokumentů a nulový počet opakovaných návrhů.
