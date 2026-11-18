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
Výjimkou je prokazatelně prázdný soubor ve složce bez shody názvu či místa.
Složka s takovým souborem zůstává obsazená. Nesouvisející nečitelný soubor
z jiného roku výběr cílové složky neovlivní.

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
- Kompaktní týmové tabulky na pozarnisporty.cz se sloupci Název, Výsledný čas
  a Čas 1/2 (P/N) zachovávají oficiální časy a pořadí družstva. Rozbalovací
  soupiska nemá vlastní výkony. Čas 00:00:00.00 je v tomto formátu zástupná
  hodnota. U požárního útoku se samostatnými proudy se ukládá oficiální výsledný
  čas a poznámky k proudům zůstávají v upozorněních. Čas celého pokusu se z proudů
  nedopočítává. Tabulky celkových bodů za víc disciplín vyžadují vlastní adaptér.
- Týmové tabulky ZHVB se sloupci pro časy a kontrolní stanoviště zachovávají
  oficiální výsledný čas a pořadí. Časy startu a cíle, mezičasy, body na stanovištích
  a rozbalovací soupisky nejsou pokusy. Disciplína zůstává null.
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

## Dávka místních krajských PDF s výsledky dorostu

Spouští se z kořene repozitáře s nainstalovanými závislostmi z
`backend/requirements-extraction.txt`. Vstup může obsahovat další podsložky.

```sh
PYTHONPATH=backend python -m app.extraction.youth_pdf /cesta/k/pdf \
  --output data --diagnostics .extraction-diagnostics/youth-pdf --dry-run
```

Po kontrole spusťte stejný příkaz bez `--dry-run`. Výsledky připravené k uložení
použijí stávající výsledkové schéma a ukládání do `data/{rok}/{závod}/`.
Dávka vrací nenulový návratový kód, pokud některý dokument vyžaduje kontrolu.
Zpracování ostatních dokumentů pokračuje.

- Převod používá geometrii tabulek a rozsahy sloupců. Ze samostatných tabulek
  a jednoznačně označených disciplín v přehledech vybírá individuální pokusy,
  výsledný čas a pořadí stovky podle toho, co zdroj skutečně publikuje. Sloupce
  PHP, bodové součty a celková pořadí vícebojů se nepřenášejí. Odvození času
  vyžaduje doložené pravidlo podle části Kontrola identity a výsledného času.
- Týmová část může obsahovat žebříček jednotlivců. Tehdy se zachová zdrojová
  kategorie a přehled ji označí jako týmovou část. Souhrnné pořadí družstev
  nevytváří další individuální výsledky.
- `batch-report.json` odkazuje na report každého PDF. Report obsahuje původní
  buňky, kategorii, čísla stránky, tabulky a řádku, souřadnice v PDF, případné
  identifikační předpony a index výsledku v kategorii. Jsou v něm také doklady
  metadat, normalizované kategorie, vyřazené položky a varování. Číselné předpony
  bez výslovného označení FSCode zůstávají v reportu.
- OCR vyžaduje Tesseract s modely `ces` a `eng`. Obrazové stránky a oblasti se
  renderují na 300 DPI. Diagnostika zahrnuje obraz, TSV, souřadnice, spolehlivost
  rozpoznaných slov a návrh jejich seskupení do řádků. Poškozený text a sloupce
  se automaticky neopravují. Kandidáty z ověřitelných částí lze najít v
  `pending.json` vedle reportu.

Ověřený přepis obrazových oblastí lze opakovat pomocí `--review cesta.json`.
Kořen tohoto souboru je objekt klíčovaný SHA-256 celého PDF z reportu. Položka
může obsahovat zdrojem potvrzené `name_order` (`surname-first` nebo
`given-first`) a objekt `regions`. Klíčem je `key` oblasti OCR z reportu.
Každá ověřená oblast má `verified: true`, volitelné `metadata_lines` a
`tables`. Tabulka uvádí `heading`, `category`, `bbox`, `rows` a případně
`name_order`. Když záhlaví výslovně neuvádí jednotlivce, doplňte původní názvy
jejich sloupců v `individual_columns`. Řádek má `bbox` v bodech PDF a
`cells` s publikovanými řetězci `rank`, `bib`, `name`, `team`, `district`,
`fscode`, `first`, `second` a `final`. Prázdný seznam tabulek potvrzuje
vizuálně zkontrolovanou oblast bez cílových výsledků. Před potvrzením ověřte
tituly disciplín, hranice sloupců a všechny řádky proti obrázku. Soubory
ověření a diagnostiky s osobními údaji ukládejte mimo Git.

Syntetické PDF v `app/tests/test_youth_pdf.py` se sestavují bez sítě.
Pro integraci s původní 24stránkovou jihočeskou listinou nastavte
`YOUTH_PDF_JIHOCESKY` na místní cestu k ní.

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

## Kontrola identity a výsledného času

Převod PDF uloží neúplná a nejednoznačná jména do reportu se zdrojovými buňkami,
stránkou, tabulkou, číslem řádku a souřadnicemi. Celá dotčená listina čeká na
ověření v diagnostice. Její `pending.json` obsahuje jen řádky s ověřenými jmény.
Databázový importér nezávisle zkontroluje jména ve všech kategoriích vstupního
dokumentu ještě před prvním zápisem nebo párováním. Chyba odmítne celý vstupní
dokument.

Pro závody, jejichž pravidla a disciplínu 100 m s překážkami lze doložit,
může ověřovací soubor pro konkrétní SHA-256 obsahovat `best_attempt_rule`
s citací nebo popisem pravidla. Pro krajské soutěže dorostu byl podkladem
[SH ČMS, pravidlo 27 odst. 5 a 9](https://mladez.dh.cz/images/Dokumenty/mladez/dorost/smernice-dorost/smernice-dorostu-2022.pdf#page=63).
Převod zachová zveřejněný čas a označí ho `published`. Nejlepší platný pokus
doplní jen při chybějícím výsledném čase a doloženém pravidle. Doplněný čas má
původ `derived_from_attempts`. Rozpor mezi publikovaným výsledkem a pokusy je
v reportu. Při výslovně neplatném výkonu nebo dvou neplatných pokusech je stav
`invalid`. Při nedostatku zveřejněných údajů je stav `missing`. V obou
případech zůstane výsledný čas `null`. Starší soubory bez údaje o původu
se dál načítají. Skript `fix_final_times.py` vypisuje kontrolu časů jako JSON
na stdout.

Osobní rekordy, časové průměry, trend a stabilita se počítají pro jednu
disciplínu. API přijímá volitelný parametr `discipline`. Bez něj dává přednost
100 m, potom 60 m. Starší výsledky bez disciplíny mohou vstoupit do samostatné
řady jedné známé kategorie, pokud sportovec nemá disciplínu uvedenou. ML
odděluje skupiny podle disciplíny a starší výsledky bez disciplíny podle ID
kategorie. Výslovné stavy `invalid` a `missing` vylučují čas ze statistik
i tehdy, když starší záznam obsahuje číselnou hodnotu.

### Audit stávajících záznamů v MongoDB

Použijte účet s oprávněním pro čtení a nastavte `AUDIT_MONGO_URL` v prostředí.
Příkaz načte jen výsledky a odpovídající profily. Vytvoří nový lokální report
s omezenými právy a ID záznamů, stavem vazeb a počty výsledků navázaných na
dotčené profily.

```sh
PYTHONPATH=backend python backend/scripts/audit_result_names.py \
  --database firesport --output .extraction-diagnostics/result-names-audit.json
```

1. Podle soutěže, kategorie, startovního čísla nebo pořadí dohledat příslušný
   zdrojový řádek. Potvrdit jméno i příjmení a identitu doložit nezávisle,
   například výslovným FSCode. Řádky bez dostatečného podkladu nechat k revizi.
2. Pro každý potvrzený řádek připravit návrh se stejným ID výsledku a očekávanou
   současnou hodnotou pole `imported_athlete` a vazby `athlete`. U navázaných
   profilů předem prověřit ostatní výsledky a účty. Návrh změny vazby posoudit
   odděleně od opravy přepisu jména.
3. Před případným schváleným zápisem pořídit cílenou zálohu, porovnat návrh se
   stavem databáze a při rozporu návrh zastavit. Po schválené opravě zopakovat
   audit a podle dopadu přepočítat dotčené statistiky a ML výstupy.
