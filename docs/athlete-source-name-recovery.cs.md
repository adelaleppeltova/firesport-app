# Obnova původního jmenného textu

Dry-run vychází z auditního čtecího snímku MongoDB s 25 951 výsledky. Prošel všech 154 řádků bez jména a příjmení. Použil zdrojové JSON v repozitáři, extrakční varování a uložené HTML v diagnostice. Všechny dotčené výsledky odkazují na HTML soutěže. Přechod na jinou PDF listinu by pro tyto řádky vyžadoval samostatný zdrojový doklad.

| Výsledek kontroly | Počet |
| --- | ---: |
| Záznamy s dohledaným původním jménem | 154 |
| Záznamy s doloženými oddělenými jmennými poli | 0 |
| Záznamy k doplnění pouze o původní celý text | 154 |
| Záznamy bez dohledatelného jména | 0 |
| Doložená propojení s profilem v aplikaci | 0 |
| Záznamy vyžadující kontrolu rozdělení a identity | 154 |
| Navrhované databázové operace | 154 aktualizací |

Celý jmenný text je u 113 řádků doložen přímo z archivovaného HTML a u 153 z extrakčního varování spojeného se zdrojovým řádkem. Podklady se překrývají. Dry-run vyžaduje odpovídající URL a datum soutěže, původní skupinu, disciplínu, pořadí, startovní číslo, klub, výsledný čas a stav a všechny pokusy ve správném pořadí. Shoda musí být jedinečná na obou stranách. Při sdíleném pořadí lze varování použít pouze se shodným explicitním startovním číslem. Každý návrh obsahuje MongoDB ID, otisk původního dokumentu, zdrojový lokátor a otisk zdrojového souboru.

## Ostrava

Oba výkony jsou ze soutěže BO stovky dne 3. října 2026. Archivované HTML uvádí účastnické jméno v jednom odkazu. Na tomto portálu výsledková tabulka běžně používá pořadí příjmení a jméno. U tříslovných řetězců však odkaz má jedinou textovou hodnotu a neobsahuje oddělená pole. Z tohoto podkladu se automaticky nepřidělují jednotlivá slova do jmenných polí ani do profilu.

| Výsledek | Řádek ve zdroji | Navržený jmenný text |
| --- | --- | --- |
| Svinov, 2010, 21,49 s | Střední dorostenci, 10. místo, pokusy 25,49 a 21,49 s | Souček Stanislav Gabriel, zachované zdrojové pořadí slov |
| Albrechtice Zámostí, 2011, 20,34 s | Střední dorostenky, 10. místo, pokusy 20,34 a 20,36 s | Popalová Monika Nora, zachované zdrojové pořadí slov |

[Oficiální listina](https://pozarnisporty.cz/races/988)

## Budoucí import a případné schválené doplnění

HTML a podporované individuální PDF extraktory ukládají původní jmenný text do volitelného pole `source_full_name` i při úspěšném rozdělení. Schéma zůstává uzavřené vůči neznámým polím a původní JSON bez tohoto pole zůstávají platné. Import ukládá text vedle oddělených polí a párování. Uspěl-li pouze přenos celého jména, zůstane stav kontroly rozdělení. Jmenný text se nepoužije pro automatické přiřazení ani založení profilu. Již uložený a jednoznačně identický řádek může při běžném opakovaném importu získat pouze chybějící jmenný text. Při rozporu mezi dvěma zdrojovými jmény pro dosud nerozdělený řádek import případ předá ke kontrole.

Administrační fronta pro aktivní jednotlivce volí oddělené jméno, celý zdrojový text nebo „Jméno nezjištěno“. Původní text mohou zobrazit i běžné a historické výsledkové listiny. Ruční přiřazení v administraci zůstává dostupné.

Ze složky backendu lze lokální plán opakovat nad stejným snímkem. Report musí mít novou výstupní cestu.

```bash
python -m scripts.recover_source_names --dry-run \
  --snapshot "$SNAPSHOT" --source-root ../data \
  --diagnostics ../.extraction-diagnostics --report "$REPORT"
```

Skript pouze vytvoří lokální dry-run. Po případném schválení aktualizace ověřit úplný předchozí dokument proti otisku, u každého řádku použít podmíněný zápis a zapsat výhradně navržená pole. Navržené změny zahrnují celý jmenný text, odkaz na doklad, stav kontroly a jeho důvod. Kategorie, pořadí, časy, identita a připojené profily se nemění.

## Předprodukční schvalovací bod

Schvalovací balíček vzniká příkazem `python -m scripts.prepare_source_name_repair --snapshot "$LIVE_SNAPSHOT" --original "$ORIGINAL_PLAN" --replay "$FRESH_PLAN" --output "$NEW_DIRECTORY"`. Obsahuje lokální BSON zálohu úplných dotčených dokumentů a plán s otisky všech řádků a zálohy. Čerstvá změna jména, vazby, obsahu nebo důkazu vyřadí dotčený dokument z plánu.

Pro tento schvalovací bod se rozsah zpřísnil na dvě pole, `source_full_name` a `source_name_evidence`. Administrace stav kontroly rozdělení odvodí z doloženého textu a prázdných oddělených polí. Příznaky párování se při této opravě v MongoDB nepřepisují.

Před schváleným zápisem se znovu ověří všechna ID, otisky a kontrolní součet zálohy. Každá aktualizace musí mít podmínku na ID a úplný předchozí BSON dokument. Zápis se zastaví při první neshodě. Pro návrat se použije BSON záloha. Pouze u dokumentu, který se stále přesně shoduje s očekávaným stavem po opravě, se obě pole vrátí do původní přítomnosti a hodnoty. Jakákoliv další změna se předá k ručnímu posouzení. Zálohu lze ověřit načtením v izolaci bez kontaktu s projektovou databází.
