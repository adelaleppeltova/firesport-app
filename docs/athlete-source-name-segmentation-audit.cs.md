# Ověření doplnění zdrojových jmen a audit rozdělení

## Výsledek schváleného zápisu

Proběhlo 154 podmíněných aktualizací podle plánu `b01caa3f2791190f6fd1d3a042df8be69afabbe0b8b7393efce8462bd5f51e80`. Každý zápis doplnil dvě pole `source_full_name` a `source_name_evidence`. Kontrola celé kolekce před opravou a po ní porovnala všech 25 951 ID a úplný obsah dokumentů. Změnilo se výhradně uvedených 154 dokumentů ve schválených polích. Obsah profilů závodníků zůstal shodný. Opakovaný dry-run nad novým čtecím exportem navrhl nula aktualizací.

Administrace vrací zdrojový text u všech 128 aktivních jednotlivých výsledků z této opravy se štítkem „Rozdělení jména vyžaduje kontrolu“. Všech 25 historických výsledků vrací text v příslušné historické listině. Zbývající výsledek zůstává ve frontě kontroly klasifikace a celý text je dostupný v uloženém dokumentu. Sestavený frontend byl nasazen a server obsluhuje novou verzi s touto podporou. Backendové testy prošly v počtu 816, frontendové v počtu čtyři. Oba lintery prošly.

## Rozdělení jména a příjmení

Audit posoudil všech 154 výsledků z 41 soutěží. Původní výsledkové listiny portálu mají společný sloupec „Jméno“. Běžné zobrazení portálu používá pořadí příjmení a jméno. U delších textů tato informace stále neurčuje hranici mezi složeným příjmením a více křestními jmény. Porovnání proto vycházelo ze zdrojového jmenného textu, soutěže a dostupného doloženého ročníku a sboru. U kandidátů z místních exportů byly oddělené sloupce ověřeny proti původní listině pořadatele. Doložení hranice polí nenahrazuje ověření identity pro vazbu na profil.

| Výsledek auditu | Počet výsledků |
| --- | ---: |
| Rozdělitelné podle doloženého pořadí původní listiny | 1 |
| Rozdělitelné s pomocí další nezávislé listiny | 21 |
| K ruční kontrole | 132 |
| Automatické změny strukturovaných jmen a vazeb na profily | 0 |

- Původní listina Svatohorských stovek zobrazuje dvě slova „Přerostová Elena“ v samotném odkazu na jméno. Poznámka o náhradě je v buňce mimo tento odkaz. Konvence pořadí i nezávislá sloupcová listina dovolují navrhnout jméno Elena a příjmení Přerostová. [Svatohorské stovky](https://pozarnisporty.cz/races/741) · [Nezávislá listina pořadatele](https://sdhmichalkovice.cz/wp-content/uploads/2026/02/OH26_SD_vysledky_14_15.pdf)
- U ostravského řádku s časem 21,49 s dokládá listina OSH Opava jméno Stanislav Gabriel a příjmení Souček. Jméno ze stejné soutěže v Opavě je spolu se sborem doloženo i v závodním portálu. [OSH Opava, str. 6](https://osh-opava.cz/wp-content/uploads/2025/06/SP25-op-celkove.pdf#page=6) · [Globus Cup Opava](https://pozarnisporty.cz/races/646)
- U ostravského řádku s časem 20,34 s dokládá sloupcová listina Českého poháru jméno Monika Nora a příjmení Popalová. Podporuje stejné rozdělení také pro další dva auditované výsledky se shodným plným jménem, ročníkem a sborem. [Výsledková listina Českého poháru](https://sport.dh.cz/images/Dokumenty/sport/pozarni-sport/CP/2025/Moravsk%C3%BD_Beroun/ml_dorky.pdf)
- Další ověřené návrhy vycházejí z oddělených polí v listinách Českého poháru, MČR a Jablonecké haly. U jabloneckých PDF má lokální audit název souboru, stranu a SHA-256. [Český pohár](https://sport.dh.cz/images/Dokumenty/sport/pozarni-sport/CP/2025/T%C5%99eb%C3%AD%C4%8D/vysledky_trebic/vysledky_100M_strdorci.pdf) · [MČR](https://sport.dh.cz/images/Dokumenty/sport/pozarni-sport/MCRvPS/2025/zeny_mcr_2025.pdf) · [Jablonecká hala](https://hala.oshjablonec.com/)

U 132 případů zůstává rozdělení otevřené. Označení jako `ml.` nebo `st.`, více křestních jmen a možná složená příjmení vyžadují potvrzení z další listiny nebo z oddělených polí pořadatele. Výsledky tohoto auditu jsou návrhy ke čtení. Žádné rozdělené jméno, FSCode ani vazba na profil nebyly zapsány.
