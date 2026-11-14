# Zadání pro Codex: Automatická extrakce výsledků požárního sportu do JSON

## 1. Hlavní cíl

Tvým úkolem je vytvořit, otestovat a následně používat spolehlivý systém pro automatické získávání výsledků závodů požárního sportu z webových stránek a PDF dokumentů.

**Uživatel bude v budoucnu zadávat pouze URL adresy.** Ty musíš automaticky provést všechny potřebné kroky od načtení zdroje až po uložení validního JSON souboru do připojeného GitHub repozitáře.

Systém musí být opakovaně použitelný, nikoli jednorázový skript pro konkrétní závod.

Hlavní požadavky:

1. Načíst všechny zadané URL.
2. Detekovat typ zdroje (HTML stránka, PDF, odkaz na výsledkovou listinu).
3. Získat úplné výsledky všech kategorií.
4. Extrahovat metadata závodu.
5. Identifikovat disciplíny.
6. Extrahovat závodníky, časy, pořadí a ostatní údaje.
7. Správně rozlišit platné a neplatné pokusy.
8. Rozpoznat důvody penalizace a přiřadit je ke konkrétním pokusům.
9. Vytvořit jeden JSON soubor pro každý závod.
10. Validovat strukturu a obsah JSON.
11. Uložit soubory do GitHub repozitáře.
12. Vytvořit commit a ideálně pull request.

**Zásadní pravidlo: Nikdy nevymýšlej, nedopočítávej ani neodhaduj chybějící údaje.**

Pokud údaj není dostupný nebo jej nelze jednoznačně rozpoznat, použij `null` a zaznamenej problém do `warnings`, pokud příslušné pole připouští `null`.

## 2. Práce s repozitářem

Nejprve prozkoumej strukturu aktuálně připojeného GitHub repozitáře.

- Respektuj existující architekturu projektu.
- Pokud už existují parsery, datové modely nebo validační funkce, využij je.
- Nevytvářej zbytečně duplicitní infrastrukturu.
- Nezasahuj do nesouvisejících částí projektu.
- Výsledky ukládej výhradně do `data/{year}/{competition-folder}/`, podle skutečného `competition.date`. Nikdy do `data/results/`. Toto pravidlo bylo upřesněno navazujícím zadáním pro ukládání výsledků.
- Každý závod ukládej jako samostatný `.json` soubor.
- Používej stabilní názvy souborů, ideálně podle data, názvu závodu a ID zdroje.
- Opětovné zpracování stejného závodu musí být idempotentní: nesmí vytvářet duplicity.

Vytvoř samostatné moduly pro:

- Získávání webového obsahu a dokumentů.
- Extrakci HTML tabulek.
- Extrakci PDF.
- OCR.
- Parsování metadat a kategorií.
- Parsování závodníků a časů.
- Zpracování důvodů penalizací.
- Validaci JSON.
- Ukládání výsledků a diagnostiku.

Preferuj Python, standardní knihovny a ověřené nástroje jako BeautifulSoup, lxml, PyMuPDF, pdfplumber, Tesseract, Playwright, pytest a jsonschema, pokud jsou pro konkrétní úlohu potřebné.

Nevytvářej složitou infrastrukturu bez důvodu. Upřednostni jednoduché, testovatelné a udržovatelné řešení.

Pravidla tohoto zadání ulož také do vhodné projektové dokumentace, například `AGENTS.md`, aby se při dalších spuštěních nemusela opakovat. Pokud takový soubor už existuje, zachovej jeho dosavadní instrukce.

## 3. Vstupní data

Vstupem je jedna nebo více URL adres.

Typický příklad:

`https://pozarnisporty.cz/races/1034`

Možné zdroje:

- Stránka závodu obsahující přímo výsledkové tabulky.
- Stránka závodu odkazující na PDF výsledkovou listinu.
- Samostatný PDF soubor.
- Webová stránka s více kategoriemi a výsledkovými tabulkami.
- Vícestránkový dokument se složitějším rozložením.

Postup zpracování:

1. Stáhni dostupný obsah zdroje.
2. Rozpoznej HTML/PDF podle skutečného obsahu, nikoli pouze přípony URL.
3. Pokud jsou výsledky přímo v HTML, preferuj extrakci z HTML.
4. Pokud jsou výsledky v připojeném PDF, stáhni PDF.
5. Pokud PDF obsahuje textovou vrstvu, použij přímou extrakci textu a tabulek.
6. Pokud je PDF skenované, obrázkové nebo je textová extrakce nespolehlivá, použij OCR.
7. U vícestránkových PDF projdi všechny stránky.
8. U HTML projdi všechny výsledkové kategorie, včetně skrytých nebo dynamicky načítaných sekcí.
9. Pokud jsou některé výsledky načítány JavaScriptem, použij odpovídající dostupné prostředky včetně browser automation.

Nezpracovávej pouze první tabulku nebo první stránku dokumentu.

Respektuj přiměřené limity požadavků a nevytvářej zbytečnou zátěž zdrojového webu.

Pokud zdroj není dostupný, nedomýšlej obsah a nepoužívej stará data jako aktuálně ověřená.

## 4. Povinná výstupní struktura

Pro každý závod vytvoř **jeden validní JSON soubor** v následující struktuře:

```json
{
  "source_file": "https://pozarnisporty.cz/races/1034",
  "generated_at": "2026-11-13T21:00:00Z",
  "competition": {
    "name": null,
    "place": null,
    "date": null,
    "league": null,
    "categories": [
      {
        "name": "mladší žáci A – dívky – od 6 do 8 let",
        "discipline": "60m",
        "results": [
          {
            "start_number": "6",
            "fscode": null,
            "first_name": "Alena",
            "last_name": "Fraňková",
            "birth_year": 2018,
            "team": "Tuhaň",
            "district": null,
            "times": [
              {
                "try": 1,
                "time": 18.70,
                "status": "valid"
              },
              {
                "try": 2,
                "time": null,
                "status": "invalid",
                "invalid_reason": "rozpojeno"
              }
            ],
            "final_time": 18.70,
            "final_status": "valid",
            "rank": 1
          }
        ]
      }
    ]
  },
  "parsing_notes": [],
  "warnings": []
}
```

Tento JSON je pouze **ilustrace struktury**, nikoli skutečný výsledek konkrétní závodnice. Hodnoty z příkladu nesmí být použity jako vstupní data.

### Datové typy

| Pole | Typ |
|---|---|
| source_file | string |
| generated_at | ISO-8601 UTC string |
| competition.name | string / null |
| competition.place | string / null |
| competition.date | YYYY-MM-DD / null |
| competition.league | string / null |
| competition.categories | array |
| category.name | string |
| category.discipline | enum / null |
| category.results | array |
| start_number | string / null |
| fscode | integer / null |
| first_name | string / null |
| last_name | string / null |
| birth_year | integer / null |
| team | string / null |
| district | string / null |
| times | array, nejvýše dva pokusy |
| times[].try | integer: 1 nebo 2 |
| times[].time | number / null |
| times[].status | valid / invalid / missing |
| times[].invalid_reason | string, nepovinné pole |
| final_time | number / null |
| final_status | valid / invalid / missing |
| rank | integer / null |
| parsing_notes | array of strings |
| warnings | array of strings |

Pokud je hodnota nedostupná, je `null` důležitější než formální požadavek na neprázdný string nebo integer.

Nevytvářej žádné další výstupní atributy v hlavním JSON.

Výjimkou je nepovinné pole `invalid_reason` uvnitř konkrétního pokusu.

JSON ukládej v UTF-8, zachovej českou diakritiku a použij skutečný čas generování v UTC.

## 5. Extrakce metadat závodu

### 5.1 Název závodu — competition.name

Hledej především:

- Hlavní nadpis stránky nebo dokumentu.
- Nadpis výsledkové listiny.
- Záhlaví PDF.
- Výrazy „Výsledková listina“, „Pohár“, „Memoriál“, „Stovkování“, „Šedesátky“, „Seriál“, „Kolo“ apod.

Rozlišuj specifické a generické názvy.

**Specifický název:**

Například:

- Stovkování pod Slunečnou
- Šedesátky pod Slunečnou
- Memoriál Jana Nováka
- O pohár starosty obce
- STIMAX CUP 2026 - 4. (finálové) kolo - Chomutov

Takový název zachovej, pokud již obsahuje jednoznačné určení závodu.

**Generický název:**

Například:

- Český pohár
- Okresní kolo
- Krajské kolo
- Seriál závodů
- Výsledková listina

Pokud je známé místo závodu a název je skutečně generický, připoj jej:

`Český pohár – Budíkovice`

Pokud místo není známé, zachovej generický název.

Striktní omezení:

- Nepřipojuj místo dvakrát.
- Nepřipojuj místo ke specifickému názvu.
- Odstraň datum závodu z názvu, pokud je uvedeno jako samostatná datumová část.
- Zachovej ročník soutěže jako součást názvu, například 2026.
- Neměň význam názvu.
- Pokud název nelze určit, nastav `null` a vytvoř warning.

### 5.2 Místo — competition.place

Hledej název města, obce nebo areálu.

Příklady:

- Chomutov
- Budíkovice
- Hradec Králové
- Atletický stadion XY

Pokud je místo spojeno s datem, odděl je.

Nikdy neodvozuj místo závodu z názvu týmu ani ze sídla pořadatele.

Pokud nelze místo jednoznačně určit, nastav `null` a warning.

### 5.3 Datum — competition.date

Rozpoznávej:

- `5.7.2025`
- `05.07.2025`
- `2025-07-05`
- `19.09.2026 08:00`

Normalizuj na:

`YYYY-MM-DD`

Použij datum konání závodu, nikoli datum publikace dokumentu, tisku nebo uzávěrky registrací.

Pokud je závod vícedenní a nelze jednoznačně určit reprezentativní datum, nevymýšlej je. Použij `null` a warning, pokud není jasně uveden začátek závodu, který lze podle zdroje použít.

### 5.4 Liga — competition.league

Hledej jednoznačné označení ligy nebo seriálu:

- Český pohár
- STIMAX CUP 2026
- Olomoucká šedesátka
- Jiný explicitně uvedený seriál

Pokud liga není uvedena nebo existuje více nejednoznačných možností, nastav `null` a warning.

Nezaměňuj název konkrétního závodu s ligou.

## 6. Kategorie

Kategorie identifikuj podle oficiálních nadpisů tabulek a dokumentů.

**Názvy kategorií zachovej přesně podle zdroje.**

Nepřeváděj je automaticky na vlastní klasifikaci a nerozděluj společné kategorie.

Běžné standardizované názvy jsou:

- Mladší dorostenky
- Mladší dorostenci
- Střední dorostenky
- Střední dorostenci
- Starší dorostenky
- Starší dorostenci
- Muži
- Ženy

Weby však mohou používat vlastní věkové kategorie, například:

- mladší žáci A – dívky – od 6 do 8 let
- mladší žáci B – dívky – od 9 do 11 let
- mladší žáci A – chlapci – od 6 do 8 let
- mladší žáci B – chlapci – od 9 do 11 let
- starší žáci A – dívky – 12 a 13 let
- starší žáci B – dívky – 14 a 15 let
- starší žáci A – chlapci – 12 a 13 let
- starší žáci B – chlapci – 14 a 15 let
- dorost dívky – 13 – 16 let
- dorost dívky + ženy – 17 – 100 let
- dorost chlapci – 13 – 16 let
- dorost chlapci + muži – 17 – 100 let

Tyto názvy jsou rovněž povolené, pokud přesně odpovídají skutečnému zdroji.

Nepřejmenovávej například `dorost dívky + ženy – 17 – 100 let` na `Ženy`.

Pokud má zdroj jednu společnou kategorii pro dorost a dospělé, zachovej ji jako jednu kategorii.

Nevytvářej kategorii, která na zdroji neexistuje.

## 7. Identifikace disciplíny

Každá kategorie musí obsahovat pole `discipline`.

Povolené hodnoty:

- `100m`
- `60m`
- `100mPHP`
- `4x100m`
- `PU`
- `vez`
- `null`

### Mapovací pravidla

| Text ve zdroji | discipline |
|---|---|
| Běh na 60 m s překážkami | 60m |
| 60 m | 60m |
| 60m | 60m |
| Šedesátky | 60m |
| Běh na 100 m s překážkami | 100m |
| 100 m | 100m |
| 100m | 100m |
| Stovky / Stovkování | 100m |
| 100m PHP / 100mP | 100mPHP |
| Štafeta 4×100 m | 4x100m |
| 4x100 / 4×100 | 4x100m |
| Požární útok / PU | PU |
| Věž / Výstup na věž | vez |

### Důležitá věková pravidla

Pro závody používající věkové rozdělení žáků:

- Mladší žáci A (6–8 let) → `60m`
- Mladší žáci B (9–11 let) → `60m`
- Starší žáci A (12–13 let) → `60m`
- Starší žáci B (14–15 let) → `60m`
- Dorost → `100m`
- Muži → `100m`
- Ženy → `100m`

Toto věkové mapování používej pouze tam, kde je disciplína skutečně takto definována pořadatelem nebo výsledkovou listinou.

Konkrétnější označení disciplíny má přednost před obecným věkovým pravidlem.

Například `100mPHP` nesmí být nesprávně rozpoznáno jako `100m`.

Při detekci preferuj:

1. Nadpis konkrétní výsledkové tabulky.
2. Nadpis kategorie v kombinaci s disciplínou.
3. Explicitní označení disciplíny v dokumentu.
4. Propozice závodu.
5. Jednoznačné věkové mapování uvedené pořadatelem.

Pokud disciplínu nelze určit, nastav `null` a warning.

## 8. Extrakce jednotlivých výsledků

Každý závodník musí mít přesně jednu položku pro svou kategorii a hlavní blok výsledků.

### 8.1 Pořadí — rank

Přebírej výhradně oficiální pořadí ze zdroje.

Na pozarnisporty.cz je to typicky sloupec `Or.`.

Možné alternativy:

- Pořadí
- Poř.
- Rank
- Umístění

Příklad:

`1.` → `1`

Nikdy pořadí nedopočítávej ze závodních časů.

Pokud není číselné pořadí uvedeno, použij `null` a warning.

Nesnaž se automaticky vytvořit pořadí bez mezer.

### 8.2 Startovní číslo — start_number

Startovní číslo ukládej jako string.

Příklad:

`"125"`

Rozpoznávej:

- Startovní číslo
- Start. č.
- St. č.
- Bib
- Číslo závodníka
- Jednoznačné číslo uvedené u jména závodníka

Na pozarnisporty.cz může být číslo v poslední závorce za jménem a krajem:

`Fraňková Alena (Středočeský) (6)`

Zde:

- start_number = `"6"`
- závodnice = Fraňková Alena
- Středočeský je kraj, nikoliv okres.

Pozor:

Sloupec `Dráha` označuje dráhu závodníka, nikoli startovní číslo.

Pokud startovní číslo není uvedeno, použij `null`.

### 8.3 FSCode — fscode

FSCode je samostatný identifikátor závodníka.

Pravidla:

- Přebírej pouze explicitně uvedený FSCode.
- Musí být tvořen nejméně čtyřmi číslicemi.
- Pokud je kratší než čtyři číslice, nastav `null`.
- Pokud chybí, nastav `null`.
- Pokud nelze jednoznačně určit, nastav `null`.
- Výstupní typ musí být integer nebo null.
- Pokud má původní identifikátor významné úvodní nuly, upozorni na tuto ztrátu formátování ve warnings.

Nikdy nezaměňuj FSCode se startovním číslem, ID webového profilu ani číslem dráhy.

### 8.4 Jméno a příjmení

Rozděl jméno na:

- `first_name`
- `last_name`

Zachovej diakritiku, původní podobu a případná vícečetná jména.

Příklad:

`Černá Berenika Emílie`

Výsledek:

- first_name = `"Berenika Emílie"`
- last_name = `"Černá"`

Pozor na víceslovná příjmení:

`Van de Kamer Olivia`

Výsledek:

- first_name = `"Olivia"`
- last_name = `"Van de Kamer"`

Pokud je rozdělení nejednoznačné, využij jednoznačné označení ve zdroji nebo propojeném profilu.

Neodhaduj sporná jména pouze podle počtu slov.

Pokud rozdělení nelze spolehlivě určit, použij `null` u neurčitelných polí a zaznamenej původní text do warnings.

### 8.5 Rok narození — birth_year

Rok narození ukládej jako integer.

Například:

`2018`

Zdroje:

- Sloupec Rok narození.
- Sloupec Nar.
- Datum narození.
- Oficiální profil závodníka dostupný prostřednictvím odkazu ve výsledkové tabulce.

Na pozarnisporty.cz bývá rok narození uveden v propojeném profilu závodníka pod označením `Narozen:`.

Pokud je profil dostupný, pokus se tento údaj získat.

**Nikdy rok narození neodvozuj z věkové kategorie a roku závodu.**

Například označení „6 až 8 let“ neopravňuje určit konkrétní rok narození.

Pokud není rok dostupný, ulož `null`.

Pokud profil existuje, ale rok narození neobsahuje, nevymýšlej jej.

Z profilů nezískávej žádné jiné osobní údaje, které nejsou potřeba pro definované JSON schéma.

### 8.6 Tým — team

Přebírej z oficiálního sloupce:

- SDH/tým
- Družstvo
- Sbor
- Team
- Organizace

Zachovej kompletní název týmu.

Například:

`Praha - Dolní Měcholupy`

Pokud jsou časy přilepené za názvem týmu, odděl je.

Příklad:

`Moravský Beroun 24,050 999,990`

Interpretuj jako:

- team = `"Moravský Beroun"`
- Čas 1 = `24.05`
- Čas 2 = neplatný

Rozdělení prováděj pouze tehdy, když odpovídá rozložení sloupců nebo jednoznačnému formátu časů.

### 8.7 Okres — district

Hledej explicitní označení:

- Okres
- Okr.
- District

Pokud je uvedeno, ulož jeho hodnotu jako string.

Pokud chybí, použij `null`.

**Nikdy nedopočítávej okres podle města, názvu SDH nebo kraje.**

Kraj není okres.

Například `(Ústecký)` ve jméně závodníka není hodnota pole `district`.

## 9. Pokusy a časy

Každý záznam musí mít pole `times`.

Standardně vytvářej dva pokusy:

```json
[
  {
    "try": 1,
    "time": 15.42,
    "status": "valid"
  },
  {
    "try": 2,
    "time": null,
    "status": "invalid"
  }
]
```

Maximální počet pokusů je dva.

Pokud zdroj obsahuje další pokusy, například Čas 3 a Čas 4, ignoruj je ve výstupní struktuře a zaznamenej jejich existenci do `parsing_notes`.

Nepoužívej třetí nebo čtvrtý pokus místo prvního či druhého.

Pokusy nesmí být mezi sebou prohozeny.

### 9.1 Povolené stavy

Každý pokus musí mít právě jeden z těchto stavů:

- `valid`
- `invalid`
- `missing`

Význam:

**valid**

Pokus je platný a má rozpoznaný naměřený čas.

**invalid**

Pokus je neplatný, penalizovaný, nedokončený, nenastoupený nebo má prázdnou hodnotu, která se podle zadání má považovat za neplatnou.

**missing**

Použij pouze tehdy, pokud zdroj výslovně uvádí, že informace o pokusu nebyla zveřejněna nebo pokus ve zdroji vůbec není evidován z důvodu, který nelze označit jako neplatný.

Důležitá priorita:

**Prázdná buňka, pomlčka nebo nevyplněný čas znamená `invalid`, nikoliv `missing`.**

Hodnota `missing` je vyhrazena pouze pro skutečně neznámý nebo nezveřejněný stav.

### 9.2 Platné časy

Podporuj například:

- `15,42`
- `15.42`
- `15,420`
- `00:15.42`
- `00:15,42`
- `01:23.06`
- `00:18.70 P`

Výstup musí být číslo v sekundách.

Příklady:

| Zdroj | time | status |
|---|---:|---|
| 15,42 | 15.42 | valid |
| 15.420 | 15.42 | valid |
| 00:15.42 | 15.42 | valid |
| 01:23.06 | 83.06 | valid |
| 00:18.70 P | 18.70 | valid |

Desetinnou čárku převáděj na desetinnou tečku.

U formátu `MM:SS.xx` proveď pouze nezbytný převod jednotek na sekundy, protože pole `time` vyžaduje číselnou hodnotu v sekundách.

Nepovažuj dlouhý čas automaticky za neplatný. I například 83.06 sekundy může být platný výkon.

### 9.3 Neplatné časy

Následující hodnoty jsou neplatné:

- `999`
- `999,990`
- `999.990`
- `998`
- `NP`
- `DNS`
- `DNF`
- `DSQ`
- `-1`
- `999990`
- `0:00-`
- `-`
- prázdná hodnota
- neplatný pokus označený `N`

U těchto hodnot nastav:

```json
{
  "time": null,
  "status": "invalid"
}
```

Další příklad:

`00:20.80 N`

Výsledek:

```json
{
  "time": null,
  "status": "invalid"
}
```

Přestože je v původním textu naměřená hodnota, pokus je označen jako neplatný.

### 9.4 Čas zakončený pomlčkou

Zvláštní pravidlo:

Pokud je na konci číselného času pomlčka, pokus je neplatný, ale naměřený čas se zachová.

Příklad:

`16:35-`

Interpretace podle tohoto formátu výsledkové listiny:

```json
{
  "time": 16.35,
  "status": "invalid"
}
```

Další příklad:

`18,42-`

Výsledek:

```json
{
  "time": 18.42,
  "status": "invalid"
}
```

Pozor:

Výslovný neplatný marker `N` má přednost před pravidlem zachování číselné hodnoty.

Pokud je zápis s pomlčkou nejednoznačný z hlediska desetinného oddělovače a minutového zápisu, nevymýšlej konverzi. Použij `null`, `invalid` a warning.

### 9.5 Zástupné časy

Některé systémy používají zástupnou hodnotu pro závodníky bez platného výsledku.

Například pozarnisporty.cz používá v některých závodech:

`30:00.00`

Pokud je prokazatelně použita jako zástupná hodnota a závodník nemá žádný platný pokus, výsledek je:

```json
{
  "final_time": null,
  "final_status": "invalid"
}
```

Nepovažuj ji automaticky za skutečný výkon 1800 sekund.

Zároveň však nevytvářej univerzální pravidlo, že každý dlouhý čas je zástupný.

Ověřuj význam podle kontextu konkrétního výsledkového systému a stavu pokusů.

### 9.6 Neprovedený nebo prázdný pokus

Příklad zdroje:

`Čas 1: 19.63 P`

`Čas 2: -`

`Důvod pen.: 2-nenastoupil`

Výsledek:

```json
"times": [
  {
    "try": 1,
    "time": 19.63,
    "status": "valid"
  },
  {
    "try": 2,
    "time": null,
    "status": "invalid",
    "invalid_reason": "nenastoupil"
  }
]
```

Nevynechávej druhý pokus jen proto, že čas není vyplněný.

### 9.7 Oficiální výsledný čas — final_time

`final_time` přebírej **výhradně z oficiálního sloupce výsledného času**.

Typické názvy:

- Výsl. čas
- Výsledný čas
- Nejlepší čas
- Final time

Nikdy automaticky nepočítej:

`min(čas1, čas2)`

Nevybírej nejrychlejší platný pokus vlastním výpočtem.

Je-li oficiální výsledný čas nedostupný, použij `null`.

Pokud je zjevně neplatný nebo odpovídá prokázané zástupné hodnotě, nastav:

- final_time = `null`
- final_status = `invalid`

Pokud výsledky ještě nebyly zveřejněny, lze použít `missing`, pokud je tento stav jednoznačně prokázán.

### 9.8 Kontrola konzistence

Zkontroluj, zda:

- Čas označený `P` má status `valid`, není-li prokazatelně zástupný.
- Čas označený `N` má status `invalid`.
- Neplatné markery nejsou interpretovány jako platný výkon.
- Prázdný čas má hodnotu `null`.
- Žádný pokus nemá jiné číslo než 1 nebo 2.
- Výsledný čas byl převzat ze zdroje.

Pokud existuje rozpor, vytvoř warning. Nikdy jej neopravuj vlastním přepočtem.

## 10. Důvody penalizací — invalid_reason

Toto je povinná součást parseru.

Ve výsledkových tabulkách hledej zejména sloupec:

`Důvod pen.`

Případně:

- Důvod penalizace
- Penalizace
- Poznámka k pokusu
- Reason
- Invalid reason

Důvod musí být přiřazen **ke konkrétnímu pokusu**, nikoliv pouze k závodníkovi.

### 10.1 Formáty zápisu

Rozpoznávej například:

- `1-rozpojeno`
- `2-rozdělovač`
- `1-obouruč`
- `1.rozpojeno`
- `2.rozpojeno`
- `1 – kladina`
- `2- rozdělovač`
- `1-kladina, 2-obouruč`
- `1-podběhl, 2-spoj`
- `1-cíl v jiné dráze, 2-obouruč`
- `1-nedoběhl, 2-nedoběhl`

Podporuj různé mezery, pomlčky a tečky oddělující číslo pokusu od důvodu.

Číslo před důvodem určuje číslo pokusu.

### 10.2 Jeden důvod

Zdroj:

`1-rozpojeno`

Výsledek:

```json
"times": [
  {
    "try": 1,
    "time": null,
    "status": "invalid",
    "invalid_reason": "rozpojeno"
  },
  {
    "try": 2,
    "time": 21.49,
    "status": "valid"
  }
]
```

### 10.3 Dva důvody

Zdroj:

`1-kladina, 2-obouruč`

Výsledek:

```json
"times": [
  {
    "try": 1,
    "time": null,
    "status": "invalid",
    "invalid_reason": "kladina"
  },
  {
    "try": 2,
    "time": null,
    "status": "invalid",
    "invalid_reason": "obouruč"
  }
]
```

### 10.4 Zachování původního textu

Hodnotu `invalid_reason` přebírej ze zdroje bez významové interpretace.

Například:

- `rozdělovač`
- `rozpojeno`
- `kladina`
- `obouruč`
- `nezapojená proudnice`
- `cíl`
- `cíl v jiné dráze`
- `nenastoupil`
- `nedokončila`
- `nedoběhl`
- `podběhl`
- `materiál`
- `spoj`

Pokud zdroj obsahuje překlep, zachovej původní text.

Nenahrazuj názvy důvodů vlastními kategoriemi.

Odstraň pouze číslo pokusu, oddělovací znaménko a nadbytečné okolní mezery.

Nepřepisuj například `cíl+rozdělovač` na jiný text.

### 10.5 Prázdný důvod

Pokud zdroj žádný důvod penalizace neobsahuje, pole `invalid_reason` vůbec nevytvářej.

Správně:

```json
{
  "try": 1,
  "time": null,
  "status": "invalid"
}
```

Nevytvářej:

```json
{
  "try": 1,
  "time": null,
  "status": "invalid",
  "invalid_reason": null
}
```

### 10.6 Nejednoznačný důvod

Pokud je uvedeno pouze:

`rozpojeno`

bez čísla pokusu a nelze bezpečně určit, ke kterému pokusu patří, nevymýšlej přiřazení.

Vytvoř warning obsahující:

- Název kategorie.
- Identifikaci závodníka.
- Pořadí.
- Původní text důvodu.

Pokud je uveden důvod pro třetí nebo čtvrtý pokus, který není v definovaném JSON schématu, zaznamenej informaci do warnings a nepřiřazuj jej k jinému pokusu.

### 10.7 Nesoulad mezi penalizací a stavem

Pokud má pokus uvedený důvod penalizace, ale ve zdroji je současně označen jako platný (`P`), zaznamenej rozpor do warnings.

Přiřaď explicitně očíslovaný důvod ke správnému pokusu, ale nepřepisuj automaticky oficiální stav bez dalšího důkazu.

## 11. Finálové běhy a duplicitní výsledky

Pokud výsledková listina obsahuje například:

- Základní kolo.
- Kvalifikaci.
- Finálový běh.
- Superfinále.

Zpracuj pouze hlavní výsledkovou tabulku příslušného závodu.

Samostatně označené bloky `Finálový běh` ignoruj.

Nepřidávej finálové pokusy jako třetí či čtvrtý pokus.

Nepřepisuj základní výsledky výsledky finále.

**Důležitá výjimka:** Název závodu obsahující například `4. (finálové) kolo` neznamená, že se má celý závod ignorovat. Jde o název kola seriálu, nikoli automaticky o samostatný blok finálových běhů.

Nevytvářej duplicitní závodníky kvůli opakovaným záhlavím, stránkám nebo tabulkám.

## 12. Vícestránkové PDF a OCR

Při extrakci PDF:

1. Zjisti celkový počet stran.
2. Projdi všechny stránky.
3. Detekuj začátky a konce jednotlivých kategorií.
4. Rozpoznej opakovaná záhlaví tabulek.
5. Správně přiřaď řádky pokračující na dalších stranách.
6. Podporuj řádky rozdělené přes více řádků textu.
7. Dávej pozor na přilepené sloupce a časy.
8. Rozlišuj textové dokumenty a obrazové skeny.
9. Pokud potřebuješ OCR, zpracuj všechny relevantní stránky.
10. Nejednoznačná OCR data kontroluj proti vizuální podobě stránky.

Při OCR zvlášť kontroluj záměny:

- `0` a `O`
- `1` a `I`
- desetinná čárka a tečka
- pomlčka a znaménko minus
- číslice v časech
- číslice ve startovních číslech
- české znaky ve jménech

Nepotvrzuj nejistý OCR výsledek jako správný pouze podle toho, že syntakticky odpovídá očekávanému formátu.

## 13. Zvláštní případy

### 13.1 Neobsazené startovní místo

Pokud řádek obsahuje:

`neobsazen`

nebo jednoznačný ekvivalent neobsazené pozice, přeskoč jej.

Nevytvářej výsledkový záznam.

### 13.2 Chybějící startovní číslo

Použij:

`"start_number": null`

Nevytvářej fiktivní číslo.

### 13.3 Chybějící FSCode

Použij:

`"fscode": null`

### 13.4 Chybějící okres

Použij:

`"district": null`

### 13.5 Chybějící rok narození

Použij:

`"birth_year": null`

### 13.6 Chybějící čas

Použij:

```json
{
  "try": 1,
  "time": null,
  "status": "invalid"
}
```

### 13.7 Dva neplatné pokusy

Oba pokusy musí mít `invalid`.

Výsledný čas bude `null`, pokud je oficiální výsledný čas neplatný nebo je zástupnou hodnotou.

### 13.8 Jeden platný a jeden neplatný pokus

Zachovej oba stavy nezávisle.

Oficiální výsledný čas převezmi ze zdroje.

### 13.9 Chybějící celý sloupec

Pokud například neexistuje sloupec okresu, nastav `district: null` pro všechny příslušné výsledky.

Vytvoř jeden souhrnný warning, nikoli stovky duplicitních upozornění.

### 13.10 Nejednoznačný údaj

Pokud existuje více možných interpretací, které nelze rozhodnout na základě zdroje, použij `null` a warning.

### 13.11 Neúplné výsledky

Pokud se nepodaří načíst všechny stránky nebo kategorie:

- Nevydávej částečný výsledek za kompletní.
- Zaznamenej přesně, co se nepodařilo zpracovat.
- Nemaž starší správně vytvořený JSON.
- Necommituj neúplná data jako dokončený import.
- Pokud je to možné, ulož diagnostiku mimo výsledný JSON a informuj uživatele.

## 14. Diagnostika — parsing_notes

Pole `parsing_notes` musí obsahovat stručné technické informace o zpracování.

Zaznamenej například:

- Zda byl zdrojem HTML nebo PDF.
- Počet zpracovaných stran PDF.
- Zda bylo použito OCR.
- Jak byly identifikovány tabulky a kategorie.
- Jak byly mapovány zdrojové sloupce.
- Jak bylo určeno startovní číslo.
- Jak byla rozpoznána disciplína.
- Jak byly interpretovány časy.
- Jak byly přiřazeny důvody penalizací.
- Zda byly použity propojené profily závodníků.

Příklad:

```json
"parsing_notes": [
  "Zdroj: HTML stránka pozarnisporty.cz.",
  "Výsledky byly extrahovány z tabulek jednotlivých kategorií.",
  "Startovní číslo bylo získáno z poslední číselné závorky za jménem závodníka.",
  "P označuje platný pokus, N neplatný pokus.",
  "Důvody penalizací byly přiřazeny podle čísla pokusu ve sloupci Důvod pen.",
  "Disciplíny byly určeny podle propozic a nadpisů kategorií."
]
```

## 15. Diagnostika — warnings

Pole `warnings` musí obsahovat problémy, nikoliv běžný průběh extrakce.

Zaznamenej zejména:

- Nejednoznačný název závodu.
- Neznámé místo.
- Neznámé datum.
- Neznámou ligu.
- Neznámou disciplínu.
- Chybějící FSCode.
- Chybějící rok narození.
- Chybějící okres.
- Chybějící pořadí.
- Nejednoznačnou identifikaci závodníka.
- Neobvyklý formát času.
- Nesoulad mezi oficiálním výsledkem a pokusy.
- Nejednoznačný důvod penalizace.
- Nesoulad důvodu penalizace se stavem pokusu.
- Neúplně zpracovanou stránku nebo kategorii.
- Nesoulad mezi počtem nalezených a deklarovaných výsledků.

Warnings musí být konkrétní a užitečné.

Pokud problém postihuje celou kategorii nebo závod, používej souhrnné upozornění místo stovek opakování.

## 16. Povinná validace

Po vytvoření každého JSON souboru proveď automatickou validaci.

### Strukturální validace

Ověř:

1. Soubor je validní JSON.
2. Má všechna povinná pole.
3. Nemá nepovolená pole.
4. Dodržuje požadované datové typy.
5. generated_at je validní ISO-8601 UTC.
6. Datum závodu má formát YYYY-MM-DD.
7. Discipline obsahuje pouze povolené hodnoty.
8. Status obsahuje pouze valid, invalid nebo missing.
9. Každá kategorie má pole results.
10. Každý závodník má povinná pole.
11. Každý výsledek má nejvýše dva pokusy.
12. Každý pokus má správné číslo.
13. invalid_reason je vždy string, pokud existuje.
14. Soubor je kódován v UTF-8.

### Obsahová validace

Ověř:

1. Počet extrahovaných kategorií odpovídá skutečně nalezeným kategoriím ve zdroji.
2. Počet výsledků v každé kategorii odpovídá zdrojové tabulce.
3. Neexistují nechtěné duplicitní záznamy.
4. Žádný závodník nebyl vynechán kvůli stránkování.
5. Žádný řádek `neobsazen` nebyl uložen jako závodník.
6. Časy byly správně převedeny na sekundy.
7. Neplatné markery nebyly uloženy jako platné časy.
8. Výsledné časy odpovídají oficiálnímu zdroji.
9. Pořadí odpovídá zdroji.
10. Každý očíslovaný důvod penalizace je přiřazen správnému pokusu.
11. Nebyly ztraceny důvody pro oba pokusy.
12. Kraj nebyl zaměněn za okres.
13. Číslo dráhy nebylo zaměněno za startovní číslo.
14. FSCode nebyl zaměněn za jiný identifikátor.
15. Rok narození nebyl odhadnut.

Nepředpokládej, že pořadí musí být souvislé, pokud oficiální zdroj obsahuje mezery či speciální výsledky.

Počet registrovaných závodníků také nemusí nutně odpovídat počtu zveřejněných výsledků. Případný rozdíl prověř a případně zaznamenej, ale automaticky jej nepovažuj za chybu parseru.

### Zvláštní kontrola penalizací

Porovnej počet jednoznačně očíslovaných důvodů penalizace ve zdrojových řádcích s počtem vložených polí `invalid_reason`.

Tyto počty by se měly shodovat, pokud neexistují výslovně zaznamenané výjimky.

## 17. Automatické testy

Vytvoř testy minimálně pro následující situace:

- Platný čas s desetinnou čárkou.
- Platný čas s desetinnou tečkou.
- Platný čas s minutami.
- Čas s označením P.
- Čas s označením N.
- Čas 999.
- Čas 999,990.
- Čas NP.
- Čas DNS.
- Čas 0:00-.
- Čas 16:35-.
- Prázdný čas.
- Nenastoupený pokus.
- Zástupný výsledný čas 30:00.00.
- Jeden neplatný pokus.
- Dva neplatné pokusy.
- Jeden důvod penalizace.
- Dva různé důvody penalizace.
- Stejný důvod u obou pokusů.
- Zápis `2- rozdělovač`.
- Zápis `2.rozpojeno`.
- Nejednoznačný nečíslovaný důvod.
- Chybějící FSCode.
- FSCode kratší než čtyři číslice.
- Chybějící okres.
- Chybějící rok narození.
- Víceslovné příjmení.
- Dvě křestní jména.
- Startovní číslo v závorce.
- Rozlišení startovního čísla a dráhy.
- Přilepené časy k názvu týmu.
- Přechod mezi kategoriemi na stránkách PDF.
- Řádek `neobsazen`.
- Ignorování samostatného finálového běhu.
- Zachování oficiálního pořadí.
- Správné rozlišení 60m a 100m.
- Případ s neznámou disciplínou.

Pokud používáš pozarnisporty.cz/races/1034 jako regresní příklad, referenční stav stránky má 12 kategorií a 416 výsledkových záznamů. V dříve zpracovaném výstupu bylo identifikováno 76 očíslovaných důvodů penalizace u 68 závodníků. Tyto hodnoty použij jako kontrolní referenci po novém ověření zdroje, nikoli jako pevně zakódované obecné pravidlo.

Všechny testy musí být opakovaně spustitelné bez nutnosti stahovat celý web.

## 18. Kontrola kvality extrakce

Po dokončení vytvoř interní souhrn:

- Počet zpracovaných URL.
- Počet úspěšně zpracovaných závodů.
- Počet kategorií.
- Celkový počet výsledků.
- Počet platných a neplatných pokusů.
- Počet pokusů s invalid_reason.
- Počet chybějících FSCode.
- Počet chybějících roků narození.
- Počet chybějících okresů.
- Počet warnings.
- Počet chyb validace.

Použij tyto informace k odhalení případných chyb parseru.

Kontrolní souhrn nemusí být součástí hlavního JSON, protože jeho struktura je pevně definovaná.

## 19. GitHub workflow

Po úspěšné extrakci:

1. Vytvoř validní JSON soubor pro každý závod.
2. Ulož jej do odpovídající složky v repozitáři.
3. Spusť všechny testy.
4. Spusť validaci JSON Schema.
5. Zkontroluj změny oproti existujícím datům.
6. Ujisti se, že neodstraňuješ žádné platné výsledky bez důvodu.
7. Vytvoř odpovídající Git commit.
8. Pokud je to možné, pushni změny do pracovní větve.
9. Vytvoř pull request.

Preferuj pull request před přímým zápisem do hlavní větve, pokud není v projektu stanovený jiný postup.

Nevkládej do repozitáře přístupové tokeny, cookies ani jiné citlivé provozní údaje.

Pokud nemáš oprávnění k zápisu nebo přístup na web, jasně označ, která operace se nepodařila. Netvrď, že byly soubory uloženy na GitHub, pokud se to skutečně nestalo.

## 20. Kritická omezení

Dodržuj bez výjimky:

- Žádné domýšlení údajů.
- Žádné odhadování roku narození.
- Žádné odvozování okresu.
- Žádné dopočítávání pořadí.
- Žádné dopočítávání výsledného času z pokusů.
- Žádné zaměňování kraje a okresu.
- Žádné zaměňování dráhy a startovního čísla.
- Žádné zaměňování FSCode a jiných identifikátorů.
- Žádné automatické přejmenování kategorií.
- Žádné rozdělování společných kategorií.
- Žádné slučování samostatných závodů.
- Žádné nahrazování prvního či druhého pokusu jiným pokusem.
- Žádné ignorování důvodů penalizace.
- Žádné přiřazování nečíslovaného důvodu k náhodnému pokusu.
- Žádné vydávání neúplných výsledků za úplné.
- Žádné nepovolené rozšíření JSON schématu.

V případě rozporu mezi zdrojem a předpokladem parseru má přednost zdroj, ale nejednoznačnost musí být zaznamenána.

## 21. Výsledné chování

Po prvním vytvoření systému bude uživatel zadávat pouze URL adresy, například:

```text
https://pozarnisporty.cz/races/1034
https://pozarnisporty.cz/races/1035
```

Ty následně automaticky:

1. Načteš zdroje.
2. Získáš výsledky.
3. Zpracuješ všechny kategorie.
4. Určíš disciplíny.
5. Extrahuješ časy a penalizace.
6. Doplníš pouze skutečně dostupné informace.
7. Vytvoříš validní JSON.
8. Spustíš testy.
9. Uložíš výsledky do GitHub repozitáře.
10. Vytvoříš commit / pull request.
11. Oznámíš uživateli výsledek a případné problémy.

Neptej se na informace, které lze jednoznačně získat ze zdroje nebo existujícího repozitáře.

Pokud se objeví nový formát výsledkové listiny, uprav parser tak, aby jej dokázal zpracovat i v budoucnu, a přidej odpovídající regresní test.

**Cílem je dlouhodobě spolehlivý, automatizovaný a testovaný import výsledků požárního sportu, který ke každému dalšímu použití vyžaduje pouze seznam URL adres.**

Začni kontrolou repozitáře a implementací kompletního systému podle tohoto zadání. Pokud jsou již v konverzaci uvedené URL adresy, použij je jako první import a ověř na nich funkčnost řešení.