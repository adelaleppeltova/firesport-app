# Automatický import výsledků z URL

Pipeline je oddělená od existujícího importu JSON do MongoDB. Nemění běžící aplikaci
ani databázi. Úplné zadání a pravidla jsou v [extraction-request.cs.md](extraction-request.cs.md).

## Instalace a použití

Z kořene repozitáře (Python 3.12+):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
cd backend
../.venv/bin/python -m app.extraction https://pozarnisporty.cz/races/1034
../.venv/bin/python -m pytest app/tests
../.venv/bin/python -m ruff check app main.py scripts
```

Lze zadat více URL oddělených mezerami. Každá se zpracuje samostatně; chyba jedné
nezastaví ostatní. Nenulový návratový kód znamená alespoň jeden neúspěšný import.
`--output` a `--diagnostics` umožňují vlastní adresáře. Výchozí cesty jsou relativní
ke kořeni repozitáře, nikoliv pracovnímu adresáři.

Výstup: `data/results/<sha256-kanonické-URL-prvních-16-znaků>.json`.
Název zůstává stabilní při opravě názvu či data soutěže. Stejný obsah nemění soubor
ani čas generování; skutečně změněný obsah získá aktuální UTC čas. Snížení počtu
výsledků/kategorií blokuje přepis a vyžaduje kontrolu opravy zdroje.

Diagnostika: `.extraction-diagnostics/<ID>/source.html|pdf`, `audit.json`,
`report.json`; pro PDF navíc text všech stran a případné OCR obrázky/TSV. Tento
adresář je v `.gitignore`. Report uvádí počty výsledků, stavů pokusů, penalizací,
chybějících identifikátorů, warnings a chyb validace. Neúspěšný import nemění JSON.

## Podporované zdroje a bezpečné meze

- `pozarnisporty.cz/races/...`: všechny HTML tabulky včetně skrytých sekcí;
  kontrola proti seznamu kategorií a deklarovaným počtům. Explicitní propozice
  umožňují věkové mapování disciplín. Profily ze stejné domény se načítají kvůli
  roku narození, nikoliv pro odhad FSCode z ID profilu. Minimálně 0,3 s mezi
  požadavky, timeout 30 s, limit 30 MB, cache během běhu.
- Obecné HTML s rozeznatelnými záhlavími a oficiální kategorií v caption/h2/h3/h4.
  Samostatné sloupce jména a příjmení mají přednost. U společného jména musí být
  pořadí zdroje doložené (`data-name-order="surname-first"`) nebo použita čárka.
  Sporná víceslovná jména zůstávají null; původní text je ve warnings.
- Textové PDF s ohraničenými tabulkami, rozeznatelnými sloupci a explicitními
  nadpisy `Kategorie: ...`. Pokračování na další straně se slučuje, opakovaná
  záhlaví se vynechávají. Nejasné slité/zalomené řádky zastaví import.
- HTML rozcestník s jediným výsledkovým PDF. Více příloh vyžaduje adaptér, aby se
  nesloučily samostatné závody. Je-li HTML výsledková tabulka, má přednost.
- Volitelný dynamický fallback: `pip install playwright`, `playwright install
  chromium`, poté `--browser`. Automatizace načte vykreslené tabulky. Nevyřešené
  stránkování či chybějící kategorie publikaci blokují.
- OCR: Tesseract v PATH a jazyky `ces+eng`. Obrazové/poškozené stránky se renderují
  v 300 DPI. OCR slouží jako podklad pro vizuální ověření a nový adaptér; samotný
  syntakticky platný OCR text není důkazem správnosti. OCR import se bez takového
  ověření nepublikuje. Nejde o univerzální autonomní parser libovolného skenu.

Chybějící metadata se označí null a warnings; neznámé rozložení se neodhaduje.
Nový formát se doplňuje v příslušném modulu a musí mít offline regresní fixture.
CLI samo neprovádí Git operace; agent po úspěšné validaci vytvoří commit a PR.

## Moduly a ověření

`fetch.py`: HTTP/browser; `html.py`: tabulky, kategorie a audit;
`pdf.py`: všechny PDF stránky; `ocr.py`: OCR diagnostika;
`metadata.py`: metadata a disciplíny; `participants.py`: identity;
`times.py`: časy; `penalties.py`: očíslované důvody;
`validation.py` + JSON Schema: struktura a obsah;
`storage.py`: idempotentní atomické uložení a kontrolní souhrn;
`__main__.py`: více URL, diagnostika a návratový kód.

`app/tests/test_extraction.py` běží bez sítě. Fixture `race-1034.html` je zmenšený
snímek skutečného HTML ověřeného 13. 11. 2026 (jen výsledkové tabulky, metadata,
propozice; bez skriptů a kontaktů). Reference 12 kategorií, 416 výsledků, 76 důvodů
u 68 výsledků patří pouze této fixture, není zakódována do parseru.

Při změně zdroje porovnejte audit řádků, počty kategorií a důvodů, oficiální pořadí
a výsledné časy; vizuálně zkontrolujte nejednoznačnosti. Poté spusťte celé backend
testy a lint, zkontrolujte diff, commitněte pouze související soubory, pushněte
pracovní větev a otevřete PR. Starší JSON z jiných složek automaticky nemigrujte.

Současný databázový model má jen valid/invalid, číselné startovní číslo a vlastní
normalizaci kategorií. Tento zdrojový kontrakt navíc uchovává missing,
invalid_reason a přesné kategorie. Pro jejich bezeztrátové zpřístupnění v aplikaci
je nutná samostatná změna databázového importu/API; CLI databázi samo neplní.
