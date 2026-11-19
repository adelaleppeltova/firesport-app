# Ověření historických kategorií a duplicit

[Novější analýza družstevních a historických listin](category-migration-published-standings.cs.md) obsahuje aktualizovaný dry-run.

Druhý dry-run vychází ze stejného obsahu projektové MongoDB jako předchozí report. Ověřila jsem shodu původního otisku před spuštěním nových pravidel. Snímek vznikl čtením a celý nový výpočet proběhl nad lokálním souborem. Výsledné počty jsou plánovaným dopadem, ostrá migrace čeká na schválení.

| Metrika | Před úpravou | Po úpravě |
| --- | ---: | ---: |
| Celkový počet výsledků | 25 951 | 25 951 |
| Zařazené výsledky | 21 244 | 22 721 |
| Nevyřešené výsledky | 4 641 | 2 768 |
| Výsledky věže | 66 | 66 |
| Skupiny možných duplicit čekající na posouzení | 396 | 0 |
| Potvrzené skutečné duplicity, počet párů | Neznámý | 396 |
| Nadbytečné kopie určené do archivu | 0 | 396 |
| Chybějící reference | 0 | 0 |

Přibylo **1 477** aktivních výsledků. Všech 21 244 dříve zařazených výsledků zůstává aktivních. Plán kontroluje zachování původních odkazů na soutěž a kategorii, pořadí, pokusů, výsledných časů, stavů i importované identity. Součet aktivních, nevyřešených, archivovaných kopií a výsledků věže zůstává 25 951.

## Rozpad původních 4 641 nevyřešených výsledků

| Příčina | Počet | Ověření a bezpečný postup |
| --- | ---: | --- |
| Jmenovitý výkon člena družstva na MČR | 1 242 | Ročníky Svitavy 2019, Zábřeh 2021, Ústí nad Labem 2022, Domažlice 2023, Písek 2024 a Kolín 2025 publikovaly měřené běhy členů družstev. Tyto řádky potřebují samostatné zobrazení v rámci družstevní soutěže. |
| Chybějící ročník v jiné kombinované nebo obecné kategorii 100 m | 503 | U sedmi výsledků se podařilo použít již ověřenou identitu a shodný ročník z nezávislého závodu s unikátním FSCode. |
| Existující ročník, ale nedoložený individuální řádek | 20 | Ověřit původní startovní číslo a konkrétní řádek hlavní výsledkové listiny. |
| Označení mladší A/B na 60 m bez uvedeného rozsahu | 982 | Propozice doložily význam všech prověřovaných zkratek. Z 651 řádků B je 647 aktivních. Ze 331 řádků A se stal známý nesoulad rozsahu 6–8 let. |
| Odlišný nebo nejasný věkový rozsah 60 m | 905 | U 307 řádků pořadatel doložil obecnou starší kategorii 11–15 let. Aktivních je 301. |
| Věk v rozporu s výchozím kanonickým rozmezím | 389 | U doložených otevřených nebo společných listin šlo použít skutečné rozmezí konkrétního závodu. Z této skupiny je nyní aktivních 210 výsledků. |
| Možná duplicitní kopie oficiálního výsledku | 525 | Porovnání s originály uvolnilo 263 aktivních výsledků a určilo 262 těchto řádků k archivaci. Dalších 134 archivovaných kopií bylo původně vedeno pod rozporem věku. |
| Nejasné pohlaví v názvu kategorie 100 m | 29 | Původní listina Bzučanského stovkování uvádí vedle krátkých titulků mužské kategorie 13–14 a 15–16 let. Všech 29 řádků je zařazeno. |
| Věk mimo kombinované rozmezí | 21 | Chomutov 2023 pro 20 řádků dokládá start od 17 let včetně. |
| Možný zástupný výsledný čas | 24 | Ověřit zdrojový čas, stav obou pokusů a pravidla časomíry. |
| Typ řádku bez doložené identity | 1 | Ověřit strukturu a původní řádek listiny. |

Označení mladší B je použito pouze pro doložených sedm závodů STIMAX v Děčíně 2023, na všech čtyřech kolech 2024 a v Děčíně a Chomutově 2025. U mladšího A se samostatně ukládá doložené rozmezí 6–8 let. Věková pravidla z jiných ročníků a stejně pojmenované listiny vyžadují vlastní doklad. [Děčín 2023](https://kshusti.hasicovo.cz/file/edee/ms-ksh/ksh-usteckeho-kraje/2024/03/clanek-stimax-cup-2023-3.-kolo-decin-2.-9.pdf) · [Propozice 2024](https://kshusti.hasicovo.cz/file/edee/ms-ksh/ksh-usteckeho-kraje/2024/03/stimax-cup-2024-propozice.pdf) · [Propozice 2025](https://kshusti.hasicovo.cz/file/edee/ms-ksh/ksh-usteckeho-kraje/2025/02/stimax-cup-2025-propozice.pdf)

Otevřené MČR v Praze používalo rozsah 15–100 let. Bludov v letech 2019 a 2022 publikoval společné listiny dospělých a staršího dorostu. Pro Bludov 2018 všech 52 dotčených řádků odpovídá publikovanému startovnímu číslu, celému jménu a ročníku v hlavních listinách. Korekce Chomutova 2023 vychází z věkového pole 17–100 v hlavním bloku pořadatele. Evidence se ukládá vedle původního názvu. [Praha 2023](https://pozarnisporty.cz/races/271) · [Archiv Bludova](https://stovky.cz/bludov/bludov.htm) · [Chomutov 2023](https://pozarnisporty.cz/races/227) · [Bzučanské stovkování](https://pozarnisport.hasicovo.cz/races/196)

## Zbývajících 2 768 řádků

| Příčina | Počet | Doporučený postup |
| --- | ---: | --- |
| Jmenovité běhy členů družstev na šesti MČR | 1 242 | Navrhnout zobrazení individuálně měřených běhů jako součásti družstevních výsledků se samostatným režimem pro pořadí a rekordy. Oficiální součty družstev získat z oddělených tabulek. |
| Rozsah 6–8 nebo 8–11 let na 60 m | 929 | Zachovat zdrojovou skupinu a rozmezí. Jde o 826 výsledků 6–8 let, z toho 331 dříve označených A, a 103 výsledků 8–11 let. Případné další zařazení potřebuje výslovné potvrzení samostatného věkového podhodnocení pořadatelem. |
| Bez doloženého ročníku nebo individuálního řádku | 516 | U 496 výsledků dohledat doloženou identitu a ročník. U 20 zkontrolovat původní individuální řádek přes startovní číslo a listinu. Samotnou vazbu založenou na jménu či týmu považovat za podnět ke kontrole. |
| Rozpor mezi ročníkem a věkovým rozmezím kategorie | 46 | Porovnat ročník s pořadatelem, pravidly konkrétního závodu a případným dřívějším opravným výsledkem. |
| Potenciální zástupný čas | 33 | Porovnat stav v původní listině. Devět těchto rozporů se ukázalo až po objasnění kategorie. |
| Věk mimo publikovaný rozsah kombinované kategorie | 1 | Prověřit pořadatelův rozsah a zdrojový ročník. |
| Nedoložený typ jednoho řádku | 1 | Dohledat řádek v individuální nebo družstevní listině. |

Pořadatelé zveřejnili tabulky jmenovitých výkonů členů družstev zvlášť od klubových součtů. Například pravidla Písku vymezují samostatný start jednotlivců a členů družstev. Kontrola lokálních dat v těchto šesti ročnících nenašla mezi oběma záznamy shodu celé posloupnosti pokusů, startovního čísla a jména. [Svitavy 2019](https://mladez.dh.cz/index.php/sportovni-cinnost/mcr-plamen-a-dorostu/665-vysledky-mcr-druzstev-dorostu-sh-cms-v-ps-svitavy-2019) · [Zábřeh 2021](https://kshusti.hasicovo.cz/cs/o-nas/aktuality/behem-vikendu-probihalo-mcr-druzstev-dorostencu-a-zastupci-naseho-kraje-si-nevedli-vubec-spatne) · [Ústí nad Labem 2022](https://mladez.dh.cz/index.php/sportovni-cinnost/mcr-plamen-a-dorostu/1052-vysledky-druzstva-usti-2022) · [Domažlice 2023](https://mladez.dh.cz/index.php/sportovni-cinnost/mcr-plamen-a-dorostu/1183-vysledky-druzstva-domazlice-2023) · [Písek 2024](https://mladez.dh.cz/index.php/sportovni-cinnost/mcr-plamen-a-dorostu/1323-vysledky-druzstva-pisek-2024) · [Kolín 2025](https://mladez.dh.cz/index.php/sportovni-cinnost/mcr-plamen-a-dorostu/1498-mistrovstvi-cr-dorostu-v-pozarnim-sportu-2025-v-koline-privitalo-i-zahranicni-tymy)

## Všech 396 dvojic

| Soutěž | Muži | Ženy | Součet |
| --- | ---: | ---: | ---: |
| Ostravská stovka 2019 | 76 | 56 | 132 |
| O pohár HVP, a.s., Třebíč 2020 | 75 | 56 | 131 |
| Bludovská stovka 2020 | 74 | 58 | 132 |
| Dubenecké stovky 2025 | 0 | 1 | 1 |
| Celkem | 225 | 171 | 396 |

Databázový kandidát vyžaduje přesnou shodu v rámci soutěže a disciplíny včetně identity řádku, oficiálního pořadí, výsledku a obou očíslovaných pokusů se stavy. Ověření navíc dohledalo pro každý pár jediný publikovaný řádek podle startovního čísla, jména, pořadí a shody naměřených platných časů. Při čtení Ostravy byly oddělené stránky finále vynechány. U Dubence prošly kontrolou obě samostatně publikované věkové listiny a řádek byl pouze v listině středních dorostenek. Mezi posuzovanými páry tak zůstává nula nevysvětlených shod, dalších pokusů, samostatných kol nebo shod různých závodníků. Tato kontrola pokrývá skupiny z původního reportu. [Archiv Ostravy](https://stovky.cz/ostrava_poruba/ostrava_poruba.htm) · [Archiv Třebíče](https://stovky.cz/trebic/trebic.htm) · [Archiv Bludova](https://stovky.cz/bludov/bludov.htm) · [Listiny Dubence](https://www.oshtrutnov.cz/sport/vysledky/)

Plán ponechává obě databázové kopie. Nadbytečný dokument má plánovaný stav `duplicate` s odkazem na zachovaný záznam, odkazem na listinu, číslem stránky a otiskem PDF. Tam, kde zachovaný výkon zůstává nezařaditelný kvůli věku, dál čeká na ruční rozhodnutí. Pro další importy je spolehlivou prevencí jednoznačný klíč závodu, disciplíny a doložené listiny nebo kola, doplněný o startovní identifikátor a kontrolu shody pokusů. Samostatná kola mají vlastní identifikátory, takže se mohou evidovat i při shodném čase. Změněný nebo nejednoznačný záznam čeká na kontrolu.

## Opakování a schválení

Ověření lze zopakovat offline. Z adresáře `backend/` se nejprve vygenerují doklady z téhož snímku, původního reportu a místních kopií originálních PDF. Následující dry-run s doklady ověřuje otisky obou dokumentů, jejich členství ve stejném kandidátním páru a shodnou doloženou příslušnost k listině. Oba příkazy vytvářejí jen místní výstupy.

```bash
python -m scripts.review_category_duplicates \
  --snapshot "$SNAPSHOT" --candidate-report "$BASELINE_REPORT" \
  --pdf-dir "$PDF_DIR" --output "$EVIDENCE"

python -m scripts.migrate_category_catalog --dry-run \
  --snapshot "$SNAPSHOT" --evidence "$EVIDENCE" --report "$REPORT"
```

Při pozdějším schválení použijte stejný soubor dokladů i ve schváleném zápisovém příkazu. Pokud se změnily výsledky, snímek nebo doklady, sestavte nový plán a schvalte jeho nový otisk. [Bezpečný postup zálohy, ověření a případné obnovy](category-migration.cs.md)
