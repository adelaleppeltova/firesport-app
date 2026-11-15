# Párování závodníků při importu

Import posuzuje pouze nové výsledky. Pravidla PR #5 pro rozpoznání výkonu se vyhodnotí před hledáním závodníka. Opakovaný import existující řádek přeskočí, včetně jeho ručního rozhodnutí, příznaku kvality a externí provenience.

## Rozhodnutí a návrhy

- Jedinečný FSCode s alespoň čtyřmi číslicemi a přesná shoda jména i příjmení mohou vést ke stavu `matched`.
- Ručně ověřené externí ID s přesným jménem nebo známým shodným rokem narození může vést ke stavu `matched`. Známá odlišná část jména blokuje automatické přiřazení i při chybějící druhé části.
- Známý odlišný rok narození nebo FSCode, sdílený kód, rozporné vlastnictví identifikátorů a neúplné vyhledání blokují automatické rozhodnutí. Chybějící údaje se do důkazů nepočítají.
- Jméno, ročník, historický tým a podobnost jména pomáhají řadit kandidáty. Kombinace jména, ročníku a týmu bez silného identifikátoru zůstává ke kontrole. Okres se nepoužívá.
- Stav `needs_review` označuje nalezené kandidáty nebo nevyřešený identifikátor. `unmatched` označuje výsledek bez použitelného kandidáta. Administrace zobrazuje obě skupiny a načítá až deset návrhů až po otevření řádku.

Administrátor může ručně přiřadit konkrétní výsledek nebo zaškrtnout další řádky se stejným normalizovaným jménem, ročníkem, kódem, týmem a externím ID. Seskupení vyžaduje jméno a kód nebo jméno, ročník a tým. Hromadné potvrzení kontroluje shodu skupiny, známé rozpory, silné důkazy pro jiné profily a aktuální stav každého výsledku. Bez silného identifikátoru cílového profilu vyžaduje shodný ročník a nejvýše jeden řádek z každé soutěže. Souběžně změněné řádky přeskočí a vrátí jejich ID. Jednotlivé přiřazení ani vytvoření profilu nespouští přepárování dalších řádků.

Ruční přiřazení a odebrání vazby ukládají historii přímo do výsledku včetně účtu administrátora, času a ID profilu. Dřívější ruční vazby zůstávají rozpoznatelné podle původního důvodu. Historické ID v auditu označuje profil, o kterém administrátor tehdy rozhodl.

## Externí identifikátory

Zdrojový adaptér nebo administrátor může dodat doprovodná data pouze pro identifikátory, které poskytovatel označuje jako trvalé ID osoby. Číslo dráhy, pořadí nebo startovní číslo se pro tento účel nepoužívá. U administrátorského importu jednoho souboru předej multipart pole `external_identity_sidecar` jako JSON. V Pythonu slouží argument `external_sidecar` metody `DataImporter.import_from_dict`. Hodnota `payload_sha256` vzniká funkcí `payload_digest(parsed_results)`. Klíče v `categories` odkazují na pozici kategorie a řádku od nuly.

```json
{
  "payload_sha256": "<64 hex znaků>",
  "categories": {
    "0": {
      "2": {
        "provider": "example.test",
        "person_id": "70001",
        "evidence_url": "https://example.test/athletes/70001"
      }
    }
  }
}
```

Tento soubor je samostatný a nemění výsledkové JSON schéma ani identitu výkonu. Dokládá, které ID bylo ve zdroji u konkrétního řádku. Import sám neověřuje tvrzení poskytovatele.

Po kontrole odkazu a ručním potvrzení výsledku použij `POST /v1/admin/results/{result_id}/verify-external-identity` s poli `athlete_id`, `provider` a `person_id`. Endpoint vyžaduje správce a přesnou shodu s uloženým pozorováním a ručním přiřazením. Registr drží jednoho vlastníka pro klíč poskytovatel a ID osoby. Opakování stejného ověření je bezpečné a pokus o změnu vlastníka vrátí konflikt. Výsledkové potvrzení samo do registru nic nepřidává. Aktuálně se provenience ukládá jen při vložení nového výsledku a ověření registru je dostupné přes API.

## Ruční slučování profilů

Předchozí implementace měnila `results.athlete` a `users.athlete_id`. Vynechávala `anomaly_scores.athlete_id` a změny nedělala atomicky. Ručně vyžádané sloučení nyní přepíše všechny tři živé reference, ověřené externí identity a ukazatele z dříve sloučených neaktivních profilů v jedné transakci. Zachová ID dokumentů, skóre, příznaky kvality, historické rozhodnutí i zdrojový profil jako neaktivní. Rozdílné známé ročníky sloučení blokují.

Základní Docker Compose používá samostatnou MongoDB. Sloučení na této konfiguraci vrací 503 bez změn, protože atomická operace vyžaduje replica set nebo sharded cluster. Transakce zahrnuje reference existující v jejím snímku. Při ručním sloučení je potřeba pozastavit souběžné importy, úpravy přiřazení, zápisy vazeb uživatelů a běhy výpočtu anomálií, které mohou vytvářet nové reference mimo transakci. Kontrola se týkala kódu a izolovaných testů. Stav existujících referencí v produkci ani přepočet historických skóre nebyly součástí změny.

## Offline srovnání

V repozitáři nebyla dostupná sada anonymizovaných, dříve ručně potvrzených přiřazení. Syntetické případy reprezentují 18 záznamů se správným existujícím profilem a 5 případů, kde správný profil chybí. Každý případ je nezávislý. Porovnání spouští skutečnou předchozí a novou rozhodovací logiku nad izolovanými kandidáty. Předchozí algoritmus samostatné externí ID neznal.

| Metrika | PR #5 | Nová pravidla |
| --- | ---: | ---: |
| Správné automatické shody | 5 | 5 |
| Falešná automatická přiřazení | 4 | 0 |
| `needs_review` | 11 | 16 |
| `unmatched` | 3 | 2 |
| Celkem pro administrátora | 14 | 18 |
| Precision | 55,6 % | 100 % |
| Recall | 27,8 % | 27,8 % |

Předchozí verze chybovala u dvou jmenovců, neznámého ID poskytovatele a rozporu mezi FSCode a ověřeným ID. Nová verze v těchto případech odložila rozhodnutí. Získala tři správné shody díky ověřeným externím ID, zatímco tři dřívější správné shody bez silného platného identifikátoru poslala ke kontrole. Čísla popisují vybrané testovací scénáře. Provozní přesnost, recall ani pokles ručních kontrol z nich odvodit nelze.

Pro reprodukci z kořene repozitáře:

```sh
git show e9df79c1:backend/app/services/result_matching.py > /tmp/firesport-previous-matcher.py
cd backend
MONGO_URL=mongodb://127.0.0.1:1 python -m app.tests.test_matching_evaluation /tmp/firesport-previous-matcher.py
```
