# Družstevní a historické výsledkové listiny

Dry-run vychází z původního snímku projektové MongoDB. Veškeré načtení podkladů, sestavení plánu a ověření proběhlo nad lokálními soubory. Produkční migrace čeká na schválení.

| Stav | Předchozí plán | Nový plán |
| --- | ---: | ---: |
| Původní databázové záznamy | 25 951 | 25 951 |
| Záznamy po odečtení potvrzených kopií | 25 555 | 25 555 |
| Kanonicky zařazené výsledky v běžných listinách | 22 721 | 22 742 |
| Jmenovité běhy členů družstev připravené k publikaci | 0 | 1 242 |
| Historické výsledky 60 m v původních skupinách | 0 | 929 |
| Výsledky ke kontrole | 2 768 | 576 |
| Archivované duplicitní kopie | 396 | 396 |
| Archivované výsledky věže | 66 | 66 |
| Oficiální týmové položky vedené odděleně | 0 | 180 |
| Chybějící reference | 0 | 0 |

Počet 25 555 vyjadřuje původní řádky po odečtení 396 doložených kopií. Zahrnuje ruční kontrolu i věž. Týmové součty jsou samostatné záznamy výsledku družstva mimo tento počet.

## Družstva a časy členů

Výsledky členů jsou klasifikovány jako `team_member` ve dvou existujících kategoriích dorosteneckých družstev. Číslo týmu z původní listiny spolu se soutěží a kanonickou kategorií určuje identifikátor družstva. Původní řádek člena zůstává součástí importované historie. Přehled závodu zobrazuje odděleně oficiální pořadí a součet družstva a pod ním jmenovité časy členů s jejich pořadím v původní listině. Součty a pořadí přebírá z oficiálních tabulek pořadatele. Započítané časy ani pořadí se nepřepočítávají.

Ověřeno bylo 12 listin součtů a 12 listin členů ze Svitav 2019, Zábřehu 2021, Ústí nad Labem 2022, Domažlic 2023, Písku 2024 a Kolína 2025. Každý z 1 242 importovaných záznamů člena byl dohledán podle startovního čísla a pořadí, se shodným týmem a výsledným časem se stavem. Ve 35 případech jsou v přehledu pokusy ze zdrojové listiny kvůli rozporu se starým importem. Ve 13 případech se vedle importovaného jména uchovává přesný zobrazený text jména z listiny. U týmových součtů je zahrnuta také bezejmenná položka s číslem 3 a stavem DNF pro dorostence v Ústí nad Labem 2022. [Svitavy](https://mladez.dh.cz/index.php/sportovni-cinnost/mcr-plamen-a-dorostu/665-vysledky-mcr-druzstev-dorostu-sh-cms-v-ps-svitavy-2019) · [Zábřeh](https://mladez.dh.cz/index.php/sportovni-cinnost/mcr-plamen-a-dorostu/897-vysledky-mcr-druzstev-dorostu-sh-cms-v-ps-2021) · [Ústí nad Labem](https://mladez.dh.cz/index.php/sportovni-cinnost/mcr-plamen-a-dorostu/1052-vysledky-druzstva-usti-2022) · [Domažlice](https://mladez.dh.cz/index.php/sportovni-cinnost/mcr-plamen-a-dorostu/1183-vysledky-druzstva-domazlice-2023) · [Písek](https://mladez.dh.cz/index.php/sportovni-cinnost/mcr-plamen-a-dorostu/1323-vysledky-druzstva-pisek-2024) · [Kolín](https://mladez.dh.cz/index.php/sportovni-cinnost/mcr-plamen-a-dorostu/1482-vysledky-druzstva-kolin-2025)

Pořadatelé rozlišují běh člena družstva a klubový součet. Dokumentace výkonnostních tříd používá jako podklad výsledkovou listinu pořadatele. Pravidla Písku navíc vymezují samostatná startovní pole jednotlivců a družstev. Pro osobní rekord v aplikaci je potřeba schválit, zda tento typ startu připustit po ověření identity, platnosti konkrétního výkonu a vztahu k příslušné kategorii. Stávající výpočet dál zahrnuje pouze aktivní individuální výkony. [Organizační zabezpečení MČR v Písku](https://mladez.dh.cz/images/Dokumenty/mladez/MCR-Plamen-dorost/2024/dorost/OZ_MCR_dorostu_2024_Pisek.pdf) · [Výkonnostní třídy SH ČMS](https://sport.dh.cz/index.php/pozarni-sport/dokumenty/251-vykonnostni-tridy-v-behu-na-100-m-s-prekazkami-2)

Porovnání odhalilo v PDF ještě 10 řádků, které nemají protějšek mezi importovanými běhy členů. Jeden je platný běh z Domažlic 2023 a devět má v listině neplatný stav. Čísla, pořadí a zdroje jsou v novém reportu. Obnovu chybějícího platného výkonu a kontrolu zbývajících položek navrhuji provést jako samostatný audit doplnění, aby bylo možné ověřit i případné uložení pod jinou skupinou.

## Historické skupiny 60 m

V přehledu původních listin je **37 skupin**. Zahrnují 826 výsledků ve skupinách **6–8 let** a 103 výsledků ve skupinách **8–11 let**. U 331 výsledků bylo rozmezí 6–8 let doloženo pro původní označení A. Titulek z původní listiny, věkový rozsah a pořadí jsou v přehledu vedle sebe. Tyto řádky mají typ `historical`, žádný odkaz na kanonickou kategorii a samostatnou výsledkovou tabulku ve správné disciplíně. U 13 řádků s možným zástupným výsledným časem se zobrazuje „Čas k ověření“. Původní hodnota zůstává v importovaném záznamu.

## Dořešení neúplných řádků

Z původních 597 řádků se podařilo bezpečně zařadit 21. V každém případě byla ve výsledkové listině jednotlivců právě jedna shoda kategorie, startovního čísla, oficiálního pořadí, týmu, obou pokusů a výsledného času. Dvacet záznamů už mělo uvedený ročník a u jednoho stačilo doložit, že šlo o individuální řádek v kategorii 60 m. Důkaz určuje formát startu. Vazba na profil i jména zůstávají podle původního záznamu.

K ověření zůstává 496 chybějících ročníků, 46 rozporů ročníku s kategorií, 33 možných zástupných časů a jeden nesoulad s kombinovaným rozmezím. Porovnání lokálních kopií výsledků neodhalilo nový nezávislý ročník, který by bylo možné bezpečně převzít pro těchto 496 řádků. U zbývajících případů má smysl doplnit přímo doložený identifikátor nebo ročník ze zdroje, případně oficiální opravu času od pořadatele.

## Duplicity a ověření

Všech 396 archivních kopií má odkaz na existující zachovaný výsledek bez dalšího odkazu v řetězci. Z těchto zachovaných záznamů je 264 aktivních a 132 dále čeká na ověření věkové kategorie. Veřejné filtry, přehled listin, osobní rekordy a statistiky ignorují archivní kopie. U 132 čekajících případů se do veřejného žebříčku zatím nedostává žádná kopie. Předchozích 22 721 aktivních výsledků zůstává aktivních. Kontrola přes celý plán porovnala původní pořadí, startovní čísla, časy, stavy, pokusy, soutěže, týmy a vazby na profily. Vestavěné reference k týmovým součtům byly ověřeny pro každý z 1 242 běhů. Opětovné sestavení plánu nad stavem simulovaným v paměti nevyžadovalo další aktualizace.

Podklady pro opakování jsou lokálně v `.extraction-diagnostics/category-migration/`. Doklady z PDF a HTML vytvářejí `scripts.prepare_team_standings` a `scripts.review_individual_rows`. Nový dry-run použil tyto tři doklady se stejným snímkem.

```bash
python -m scripts.migrate_category_catalog --dry-run \
  --snapshot "$SNAPSHOT" --evidence "$DUPLICATES" \
  --team-evidence "$TEAMS" --individual-evidence "$INDIVIDUAL_ROWS" \
  --report "$REPORT"
```

Případné spuštění migrace vyžaduje nový aktuální snímek, ověření zálohy a schválení výsledného otisku. Do schváleného příkazu se přenesou všechny tři soubory dokladů. [Záloha a kontrolovaný postup migrace](category-migration.cs.md)
