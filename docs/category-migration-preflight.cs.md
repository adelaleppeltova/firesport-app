# Předmigrační audit kategorií a osobních rekordů

Dry-run V4 vychází ze stejného lokálního snímku jako předchozí plán. Soubor byl lokálně uložen 18. listopadu 2026 v 12:17:56. SHA-256 `2f8dc3ddf13e98b9360e20f9f8c12ef724d5d478e4e4a82d44a90e31fb263ef4`. Aktuální stav projektové MongoDB se během této kontroly nenačítal. Přírůstky, úpravy starších výsledků, změny vazeb profilů i změny zdrojových dokladů mohou ovlivnit plán, a to i při stejném počtu dokumentů.

## Osobní rekordy

Aplikace vyhodnocuje doplňkové běhy pouze pro rekord příslušné disciplíny. Platný výsledný čas musí mít protějšek v platném publikovaném pokusu. U družstev se upřednostní ověřené údaje z oficiální listiny, jestliže se liší od původního importu. Důkaz je svázán s profilem, soutěží a výsledným časem a týmový běh navíc vyžaduje doklad pravidel srovnatelnosti. Migrace uznává existující doložené párování přes jedinečný zdrojový FSCode, shodné jméno a údaje bez rozporných ročníků nebo vazeb. Tím zůstávají vyloučeny vazby podle samotného jména, klubu či neověřeného ročníku. Veřejné žebříčky podle kategorií nadále vycházejí z kanonických výsledků.

| Zdroj | Celkem | Nově způsobilé | Bez doložené identity nebo zdroje po kontrole času | Neplatný nebo nedoložený výsledný čas |
| --- | ---: | ---: | ---: | ---: |
| Běhy členů družstev 100 m | 1 242 | 0 | 1 221 | 21 |
| Historické skupiny 60 m | 929 | 0 | 902 | 27 |

Důvody v tabulce jsou vzájemně výlučné podle pořadí kontrol. Ani jeden z 2 171 importovaných řádků nemá zdrojový FSCode. U 60 m existuje deset vazeb podle jména a ročníku, které by šlo znovu prověřit, pokud pořadatel poskytne zdrojový identifikátor nebo jiný ověřitelný doklad identity. U 100 m potvrzují publikované směrnice individuální pokusy pro výpočet týmového pořadí. Pro jednotlivé řádky zatím chybí ověření srovnatelnosti dle pravidel příslušného závodu. Pro budoucí použití je v týmových dokladech podporováno pole `comparison_rules` u konkrétního člena s URL a kontrolním otiskem oficiálního dokumentu. Doklad současně vyžaduje doloženou identitu a platný výkon. [Směrnice dorostu SH ČMS](https://mladez.dh.cz/images/Dokumenty/mladez/dorost/smernice-dorost/smernice-dorostu-2022.pdf)

## Deset položek z původních soupisek

Sloupec číslo uvádí startovní číslo a pořadí. Devět listinných položek má místo jména zástupný text `xxx` a žádný platný čas. Zakládání jmenovitého výkonu by nebylo podložené. Čísla se opakují v dalších listinách téže soutěže, proto je riziko falešné shody podle samotného čísla vysoké. Důvod nepřítomnosti jmenovitého platného běhu v importu se ve zdrojových listinách neuvádí.

| Soutěž a datum | Číslo / pořadí | Jméno, družstvo | Výsledný čas a stav | Bezpečné doplnění a riziko |
| --- | --- | --- | --- | --- |
| MČR Svitavy, 5. 7. 2019 | 93 / 104 | neobsazeno, Stodůlky | ∅, DNF | Bez jmenovitého záznamu, číslo koliduje. [Listina, str. 2](https://mladez.dh.cz/images/Dokumenty/mladez/MCR-Plamen-dorost/2019/dorost/vysledky/druzstva/100m-j-dorci.pdf) |
| MČR Zábřeh, 3. 7. 2021 | 22 / 103 | neobsazeno, Michálkovice | ∅, DNF | Bez jmenovitého záznamu, opakované číslo. [Listina, str. 2](https://mladez.dh.cz/images/Dokumenty/mladez/MCR-Plamen-dorost/2021/dorost/vysledky/dorci-dr-100.pdf) |
| MČR Zábřeh, 3. 7. 2021 | 92 / 103 | neobsazeno, Malenovice | ∅, DNF | Bez jmenovitého záznamu. Shodné číslo i pořadí již má jiný řádek za Hrobce v ženské listině. [Listina, str. 2](https://mladez.dh.cz/images/Dokumenty/mladez/MCR-Plamen-dorost/2021/dorost/vysledky/dorci-dr-100.pdf) |
| MČR Zábřeh, 3. 7. 2021 | 98 / 103 | neobsazeno, Valašské Příkazy | ∅, NP | Bez jmenovitého záznamu, číslo koliduje. [Listina, str. 2](https://mladez.dh.cz/images/Dokumenty/mladez/MCR-Plamen-dorost/2021/dorost/vysledky/dorky-dr-100.pdf) |
| MČR Domažlice, 1. 7. 2023 | 94 / 105 | neobsazeno, Jáchymov | ∅, DNS | Bez jmenovitého záznamu, číslo koliduje. [Listina, str. 2](https://mladez.dh.cz/images/Dokumenty/mladez/MCR-Plamen-dorost/2023/dorost/vysledky/dorci-100m.pdf) |
| MČR Domažlice, 1. 7. 2023 | 1 / 1 | Kateřina Hlaváčová, Lišov | 17,00 s, platný. Pokusy 17,44 a 17,00 s. | Doložený zdrojový řádek lze po schválení doplnit bez vazby na profil. Na tomto snímku v dané soutěži nebyl nalezen stejný čas ani přesná shoda jména, číslo mají tři jiné řádky. Před doplněním znovu ověřit aktuální stav a zajistit jedinečnost podle listiny, skupiny a startovního čísla. [Listina, str. 1](https://mladez.dh.cz/images/Dokumenty/mladez/MCR-Plamen-dorost/2023/dorost/vysledky/dorky-100m.pdf) |
| MČR Písek, 1. 7. 2024 | 52 / 102 | neobsazeno, Výčapy | ∅, DNS | Bez jmenovitého záznamu, číslo koliduje. [Listina, str. 2](https://mladez.dh.cz/images/Dokumenty/mladez/MCR-Plamen-dorost/2024/dorost/vysledky/dorci-100m.pdf) |
| MČR Písek, 1. 7. 2024 | 91 / 102 | neobsazeno, Ratenice | ∅, DNS | Bez jmenovitého záznamu, číslo koliduje. [Listina, str. 2](https://mladez.dh.cz/images/Dokumenty/mladez/MCR-Plamen-dorost/2024/dorost/vysledky/dorci-100m.pdf) |
| MČR Písek, 1. 7. 2024 | 96 / 102 | neobsazeno, Jáchymov | ∅, DNS | Bez jmenovitého záznamu, číslo koliduje. [Listina, str. 2](https://mladez.dh.cz/images/Dokumenty/mladez/MCR-Plamen-dorost/2024/dorost/vysledky/dorci-100m.pdf) |
| MČR Kolín, 28. 6. 2025 | 37 / 104 | neobsazeno, Jáchymov | ∅, DNS | Bez jmenovitého záznamu, opakované číslo. [Listina, str. 2](https://mladez.dh.cz/images/Dokumenty/mladez/MCR-Plamen-dorost/2025/MCR_dorost_Kolin/vysledky/dorky/dorky-100m.pdf) |

## Opravy po migraci

Všech 576 výsledků zůstává v původní kolekci se stavem `review`, původní kategorií, důvodem a pořadím. Administrační rozhraní nabízí stránkovaný seznam. Dry-run ani veřejné výpočty nemění jejich vazbu na profil.

Pro přímo doloženou opravu jednoho řádku slouží `python -m scripts.review_migrated_result --snapshot "$SNAPSHOT" --result "$RESULT_ID" --proof "$PROOF"` ze složky backendu. Doklad obsahuje `source_url`, `source_sha256`, `result_sha256` původního řádku, případně doložené `birth_year` a BSON `athlete`. Příkaz kontroluje kanonické zařazení, ověřený profil a možné překryvy v soutěži. Původní pořadí, časy a skupina se nemění. Použití `--approve` s přesným vypsaným otiskem je až pro schválené okno bez souběžného importu. Živá kontrola se zopakuje před podmíněnou aktualizací jediného řádku. Nástroj řeší opravy klasifikace a existující prokazatelné identity. Oprava zdrojového času nebo doplnění chybějícího dokladu identity musí projít samostatnou kontrolou zdroje.

## Kontrola schválení

Nad lokálním snímkem bylo ověřeno všech 25 951 původních řádků, 396 dvojic s přímou vazbou, 22 kategorií, dvě disciplíny, nulový počet chybějících referencí a zachování původních pořadí. Druhé sestavení plánu po simulaci v paměti vydalo nula aktualizací. Otisk plánu V4 je `df8daa1f6fd6b92a57b49966f19c50daf019ab5229e2e082071ba4cc944e98e4`. Produkčnímu schválení musí předcházet nový export s účtem pouze pro čtení, srovnání obsahu kolekcí, aktualizace dokladů pro změněné řádky a nový dry-run. Před schváleným nasazením ověřit zálohu obnovou mimo produkci a zastavit souběžné importy. Aplikace migrace kontroluje proti schválenému snímku i změny dokumentů se stejným ID. [Postup zálohy a migrace](category-migration.cs.md)
