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

Všechny nové výsledky se ukládají výhradně do
`data/{year}/{competition-folder}/`. **Nikdy do `data/results/`.** `--output` nyní
určuje kořen dat (výchozí `data/`), nikoliv cílovou složku jednoho závodu.

Rok se bere pouze z `competition.date`. Neznámé datum zabrání uložení do finálních
dat; celý připravený JSON zůstane v diagnostice jako `pending.json` spolu s chybou.

Cílová složka se hledá podle stejné zdrojové URL nebo jednoznačné shody názvu,
data a místa závodu v existujících JSON. Samotné místo nestačí. Prázdnou vlastní
složku lze převzít jen při jednoznačné shodě rozlišujícího názvu soutěže i místa;
například `chomutov-stimax`. Existující názvy složek se nemění. Nejednoznačná
shoda a existující neidentifikovatelný JSON v cílovém roce ukládání zastaví.
Nesouvisející nečitelný historický soubor z jiného roku výběr cílové složky neovlivní.

Nová složka a název souboru používají lowercase ASCII a pomlčky. Soubor má formát
`YYYY-MM-DD-{nazev-zavodu}-{misto}.json`, například
`data/2026/chomutov-stimax/2026-09-19-stimax-cup-chomutov.json`.
Místo se neopakuje; v čitelném názvu se vynechá ročník odpovídající prefixu data
a výslovně očíslované kolo. Oficiální metadata uvnitř JSON se nijak nemění.

Stejná URL dohledá stávající soubor i po opravě názvu závodu. Existující jména
souborů jiných importů se automaticky nepřejmenovávají. Kolize názvů různých závodů
se rozliší výslovným ID závodu z URL (například `-1034`); pokud není takové ID
dostupné nebo nestačí k rozlišení, vznikne konflikt. Hash se používá jen pro
provozní diagnostiku, nikdy jako název finálního výsledku.

Stejný obsah nemění soubor ani čas generování; skutečně změněný obsah získá
aktuální UTC čas. Snížení počtu výsledků/kategorií nebo ztráta známých údajů blokuje
přepis a vyžaduje kontrolu opravy zdroje. Různé verze stejného závodu se při migraci
neslučují ani nepřepisují. JSON schéma i extrakce HTML/PDF zůstávají stejné.

### Migrace starých souborů

```bash
# Z backend/; nejprve pouze plán a konflikty:
../.venv/bin/python -m app.extraction.migrate
# Pro verzované soubory použije git mv; bezpečné přesuny provede, konflikty zachová:
../.venv/bin/python -m app.extraction.migrate --apply --git
```

Migrace porovnává existující soubory stejného závodu. Při konfliktu ponechá obě
verze beze změn a vrátí nenulový kód, ale dokončí ostatní bezpečné přesuny.
U každého přesunu ověří shodu všech bajtů a JSON validaci. Původní soubor zmizí
teprve po ověření cíle; obsah, formátování i generated_at zůstanou identické.
`data/results/` se odstraní jen po úspěšném vyprázdnění. Pro neversionované testovací
soubory lze vynechat `--git`. Skutečné přesuny a otevřené konflikty jsou popsány
v [souhrnu migrace](extraction-storage-migration.cs.md).

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
`paths.py`: výběr roku, existující složky a čitelného názvu;
`storage.py`: idempotentní atomické uložení a kontrolní souhrn;
`migrate.py`: kontrolované přesuny starých JSON beze změny obsahu;
`__main__.py`: více URL, diagnostika a návratový kód.

`app/tests/test_extraction.py` a `app/tests/test_extraction_storage.py` běží bez sítě. Fixture `race-1034.html` je zmenšený
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
