[EN](documentation-audit.md) · **CZ** · [Projekt](../README.cs.md)

# Audit dokumentace a ověření

Datum auditu: **22. 10. 2026**. Kontrolována implementace od výchozího commitu `5eafc43e` na samostatné větvi `docs/bilingual-portfolio-overhaul`. Jde o dokumentační úpravu; aplikační logika, chování modelu, data i původní notebook zůstaly zachovány. Nebyl spuštěn databázový import, přepočet, mazání kolekcí ani reset volume.

## Podklady a opravy

| Oblast | Podklady / výsledek |
| --- | --- |
| Úvod a autorství | Původní README, screenshoty a patička aplikace; EN/CZ stránky mají shodnou strukturu deseti oddílů a čtyři obrázky. Zachován název a kontext práce bez vymyšlených akademických identifikátorů. |
| Konfigurace a provoz | Compose, oba Dockerfile, entrypoint, `app/__init__.py`, databázové a autentizační služby; popsáno skutečné načtení dotenv, přednost prostředí, URL a vývojový charakter. |
| API a přihlášení | Všechny v1 routery, závislosti, frontendové hashování a modely; oddělena admin ochrana od nechráněného importu a ML. |
| Import | Seed, DataImporter, párovací a slučovací služby, modely a indexy; zdokumentována normalizace, deduplikace, kontrola, ztráta metadat a částečné zápisy. |
| ML | Konfigurace, numerický výpočet, okna, orchestrace a routery; zachovány české detaily, přidána anglická metodika, přesné parametry, skóre, ukládání a hranice selhání. |
| EDA | Notebook a `docs/analysis`; popsány vstupy, importy, pořadí a odlišné definice vůči aplikaci. |
| Testy/CI | Backendová sada, frontendové příkazy/test, `.nvmrc`, workflow; z architektury odstraněn pevný počet testů a zpřesněny skutečné spouštěče CI. |
| Licence | V kontrolovaném checkoutu nenalezen softwarový LICENSE ani formální CITATION; oprávnění zdrojů nejsou specifikována. |

Původní postup s `.env` skutečně podporuje `load_dotenv()`; explicitní Compose `env_file` v současném připojeném adresáři není nutný. Dokumentace mechanismus objasňuje bez nadbytečné změny konfigurace.

Počty lokální MongoDB z **12. 8. 2026** zůstaly datovaným historickým údajem původní dokumentace, nikoli nově ověřeným cílem importu. JSON byl znovu přepočítán: 329 souborů, 394 bloků kategorií, 13 854 řádků a data soutěží 2019-05-04 až 2025-10-04.

## Provedené kontroly

| Kontrola | Výsledek a hranice |
| --- | --- |
| `python3 docs/scripts/check_documentation.py` | Prošly relativní odkazy, lokální Markdown kotvy, jazyková navigace a shoda struktury/obrázků README; přepočteny JSON a chybějící pole. Nekontroluje externí URL ani význam překladu. |
| `git diff --check` | Bez chyb whitespace. |
| Shellové příklady | Všech 30 Bash bloků zkontrolováno pomocí `bash -n`; příkazy porovnány se skripty/konfigurací. Syntaxe není runtime ověření. |
| Generování OpenAPI bez připojení k DB | Prošlo načtení FastAPI aplikace s jednorázovým procesovým klíčem a ověření osmi dokumentovaných API operací; nejde o HTTP test. |
| `docker compose config --quiet` | Prošlo s Compose 5.3.1, včetně izolovaného override bez startu kontejnerů. |
| `python -m ruff check app main.py scripts` v backendu | Prošlo, Ruff 0.15.22. |
| `python -m pytest app/tests` v backendu | **102 prošlo**, 24 existujících datetime deprekačních upozornění; Python **3.13.14**, pytest 9.1.1, dočasné prostředí. Předepsané CI prostředí Pythonu 3.12 lokálně zopakováno nebylo. |
| `npm run lint` | Prošlo s Node **20.20.1** a existujícím `node_modules`. |
| `CI=true npm test -- --watchAll=false` | **1 sada / 1 test prošel**, existující závislosti. |
| `npm run build` | Prošlo; existující upozornění na stáří Browserslist dat. Lockfile ani závislosti se neměnily. |
| EDA bez UI | **27 kódových buněk úspěšně provedeno** v pořadí nad verzovanými JSON přes nbclient; spuštěná kopie uložena mimo repozitář. |

Backendové testovací závislosti byly instalovány podle existujících requirements pouze do dočasného prostředí. Vybrané verze: FastAPI 0.159.1, Pydantic 2.14.1, Motor 3.7.1, PyMongo 4.19.0, NumPy 2.5.4 a scikit-learn 1.9.1. Jde o záznam auditu, nikoli podporovaný lock závislostí.

EDA běželo na Pythonu 3.13.14 s pandas 3.0.6, Matplotlib 3.11.2, seaborn 0.13.2, IPython 9.17.1, nbformat 5.11.1, nbclient 0.11.0 a ipykernel 7.4.0. Instalace byla pouze do dočasného prostředí, runtime/cache i provedená kopie notebooku pod `/tmp`. Shoda historických grafů nebyla tvrzena.

První frontendový pokus vybral přes PATH nekompatibilní binárku; výběr nativního Node 20 chybu odstranil. První instalaci omezovala síť; poté proběhla se schváleným přístupem. První běh notebooku nemohl v sandboxu otevřít lokální socket kernelu; stejný čtecí výpočet úspěšně proběhl se schváleným přístupem pro lokální kernel.

## Neprovedené příkazy a operace

- Docker `up --build`, seed, dotazy MongoDB, živé HTTP kontroly, přepočet a vypnutí/úklid: `docker info` potvrdilo neběžící daemon. Žádné aktuální databázové počty ani analytické výsledky nejsou tvrzeny.
- Čerstvé `npm ci`: kontroly použily již nainstalované závislosti; nejde o ověření čisté instalace.
- Testy na Pythonu 3.12: pro dočasné prostředí byl dostupný pouze Python 3.13.
- Externí odkazy, živý stav badge/workflow a získání práce či zdrojů: nebyly stahovány; lokální cíle odkazů byly zkontrolovány.
- Produkční nasazení: nebylo prováděno ani popsáno existující vývojovou konfigurací.

## Překážky reprodukce a omezení implementace

1. Validním nespárovaným výsledkům může chybět `athlete`, na který ML seskupení odkazuje bez filtru. Úspěšný běh po úplném čerstvém importu nelze slíbit bez kontroly identit. Budoucí práce potřebuje explicitní pravidlo způsobilosti a regresní test.
2. Administrace potřebuje přidělenou roli; UI registrace vytváří `user` a automatický bootstrap prvního administrátora chybí.
3. Seed maže šest kolekcí a ponechává účty, jejichž párování může zastarat. Sbírání chyb a cache příznaků komplikují přesnou rekonstrukci.
4. Odstranění ne-konečných hodnot může posunout uložená skóre vůči řádkům. Nahrazení běhu a zápis skóre nejsou transakční; předchozí skóre se mažou.
5. Chybějí zdrojové listiny, URL, extrakční kód, lock prostředí a historie ručních databázových úprav. Historický lokální stav nelze přesně rekonstruovat.

Omezení jsou popsána bez změny aplikačního chování v rámci dokumentačního zadání.

## Rozhodnutí vlastníka repozitáře

- Zvolit softwarovou licenci; samostatně vyjasnit práva ke zdrojům/datasetu, soukromí, uchovávání, opravy a identifikovatelné screenshoty.
- Dodat ověřená formální citační metadata a odkaz na práci, pokud mají být zveřejněny; potvrdit způsob citování.
- Rozhodnout o prvotním přidělení admin role a oprávnění k importu/přepočtu před veřejným provozem.
- Rozhodnout, zda se validní nevyřešené výsledky z ML vyloučí, odmítnou či nejprve ručně přiřadí; bez tichého zahazování.

## Doporučené navazující práce

Prioritou je izolovaný integrační běh Docker/import/identity/ML na Pythonu 3.12 s kontrolou způsobilosti a částečných selhání. Následuje uzamčení backendových/EDA závislostí a obrazů, manifest provenience s právy, oprava popisků pokrytí a chybějícího roku v notebooku a transakční uchování běhů. Kontextové či hierarchické modelování a označená evaluace jsou návrhy výzkumu, nikoli implementované funkce.

Při další údržbě dokumentace spusťte:

```bash
python3 docs/scripts/check_documentation.py
git diff --check
```

## Změněné a vytvořené soubory

| Stav | Soubory |
| --- | --- |
| Upravené | [README](../README.md), [Copilot pokyny](../.github/copilot-instructions.md), česká [architektura](architecture.md), [data](data-baseline.md), [ML](ml-baseline.md) |
| Nové úvodní/technické dokumenty | [České README](../README.cs.md), anglická [architektura](architecture.en.md), [data](data-baseline.en.md), [ML](ml-baseline.en.md) |
| Nové průvodce reprodukcí | [EN](reproducibility.md), [CZ](reproducibility.cs.md) |
| Nové EDA průvodce | [EN](notebooks/README.md), [CZ](notebooks/README.cs.md) |
| Nové podpůrné materiály | [Galerie](screenshots/README.md), [kontrolní skript](scripts/check_documentation.py), audit [EN](documentation-audit.md) a [CZ](documentation-audit.cs.md) |

Celkem 5 upravených a 12 nových souborů. Nový kontrolní skript používá pouze standardní knihovnu a neprovádí databázové operace.
