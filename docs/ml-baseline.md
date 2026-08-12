# ML baseline

Tento dokument popisuje implementovaný stav detekce neobvyklých výkonů v M0. Neobsahuje nové experimenty, měření přesnosti ani vědecké závěry.

## Účel

Backend používá jednorozměrný Isolation Forest k označení časů, které se v historii konkrétního závodníka a skupiny porovnatelných kategorií liší od ostatních výkonů v daném časovém okně. Výstup je podpůrný analytický signál; sám o sobě neprokazuje chybu dat ani mimořádný výkon.

## Vstup a výběr výsledků

Jediným vstupním rysem modelu je `results.final_time`. Pro jedno časové okno služba `recompute_for_window` načte výsledky splňující současně:

- `final_time_status == "valid"`,
- `final_time` není `null`,
- `date` leží včetně obou hranic okna.

Výsledky se seskupí podle dvojice `(athlete_id, category_group)` a každý celek se modeluje samostatně. Pevná mapa kategorií vytváří skupiny:

- `muz`: muži, dorostenci, starší dorostenci, společné kategorie mužů a starších dorostenců a muži HZS,
- `zena`: ženy, dorostenky a jejich věkové kategorie včetně společné kategorie žen a starších dorostenek,
- `mladsi_dorostenci`: mladší a střední dorostenci včetně varianty názvu `Dorostenci střední`.

Neznámý normalizovaný název tvoří vlastní skupinu. Pokud se ID kategorie nepodaří najít v mapě načtených kategorií, jako identifikátor skupiny se použije její ID; chybějící kategorie používá `unknown`.

`quality_flag="suspicious"` není filtrem ML vstupu. Takový výsledek do Isolation Forest vstoupí, pokud splní pravidla validity výše.

## Časová okna

Výchozí `window_type` je `yearly_3y`. Anchor je 31. prosinec daného roku v UTC a tříleté okno je inkluzivní:

```text
window_end   = anchor
window_start = anchor - 3 roky + 1 den
```

Pro anchor `2025-12-31` tedy vznikne okno `2023-01-01` až `2025-12-31`. Sousední roční tříletá okna se záměrně překrývají. Funkce `list_year_anchors` generuje 31. prosinec každého roku v požadovaném rozsahu; i neúplný poslední kalendářní rok dostane anchor na konci tohoto roku.

Endpoint `POST /v1/ml/recompute-yearly` použije zadané datumové meze, nebo minimum a maximum `results.date`. Při `force=false` přeskočí již existující aktivní běh pro anchor. Při přepočtu je starý běh označen `is_superseded=true`, jeho skóre se odstraní a nový běh dostane nové `run_id`.

## Minimální počet a ochranné podmínky

Model vyžaduje nejméně 10 validních výsledků pro jednu dvojici atleta a skupiny kategorií v daném okně. Menší skupina se přeskočí s důvodem `not_enough_data`.

`compute_iforest_anomalies` před výpočtem odstraní `NaN` a kladné či záporné nekonečno. Pokud po čištění zůstane méně než minimum, důvod je `not_enough_data_after_cleaning`. Pokud je směrodatná odchylka časů podle `numpy.std` menší než `0.01` s, výpočet se přeskočí jako `low_variance`.

## Parametry Isolation Forest

Výchozí konfigurace `AnomalyConfig` je neměnná a používá:

| Parametr | Hodnota |
| --- | --- |
| vstupní rys | `final_time` |
| `min_results` | `10` |
| `contamination` | `"auto"` |
| `n_estimators` | `200` |
| `random_state` | `42` |
| `eps_std` | `0.01` |
| `n_jobs` | `-1` |
| `max_samples` | výchozí hodnota scikit-learn `"auto"` |

Pipeline neurčuje vlastní podíl anomálií ani vlastní kvantilový práh.

## Skóre, klasifikace a směr

Po fitu na jednosloupcové matici časů se počítá:

```text
score = -model.decision_function(X)
```

Skóre slouží k řazení a zobrazení míry odlehlosti. Příznak `is_anomaly` se neurčuje samostatným prahem v aplikaci, ale přímo výsledkem `model.predict(X) == -1`.

Medián se počítá z vyčištěných časů daného atleta, skupiny kategorií a okna. Pouze u označené anomálie je čas pod mediánem `fast`, nad mediánem `slow`; shoda s mediánem a všechny neanomální výsledky mají `none`.

## Ukládané výstupy

Jeden úspěšný window-level běh uloží do `anomaly_runs`:

- identifikátor a čas vytvoření,
- typ, začátek, konec, délku okna a použité minimum výsledků,
- název modelu, parametry, rys a definici skóre,
- stav a statistiky `processed`, `skipped`, `failed`, `scores_inserted` a počty důvodů přeskočení.

Pro každý výsledek úspěšně zpracované skupiny se do `anomaly_scores` uloží `run_id`, odkazy na atleta a výsledek, datum a čas výkonu, skóre, medián, příznak anomálie, směr, contamination režim a skupina kategorií. Neukládají se tedy jen anomálie, ale všechny skórované výsledky skupiny.

API `GET /v1/athletes/{athlete_id}/anomalies` umí vybrat konkrétní běh, anchor nebo nejnovější aktivní roční běh a volitelně filtrovat `category_group`. Při čtení doplní ze zdrojového výsledku soutěž a `quality_flag`.

## Quality flag versus Isolation Forest

`quality_flag` je oddělené deterministické pravidlo uložené přímo u výsledku:

1. validní čas mimo 1. až 99. percentil stejné konkrétní kategorie, s absolutními mezemi 11–45 s, je `suspicious`,
2. při alespoň pěti dřívějších validních výsledcích stejného atleta a kategorie je `suspicious` také čas vyšší než 125 % jejich mediánu,
3. invalidní nebo chybějící čas dostává `ok`.

Isolation Forest používá skupiny porovnatelných kategorií a tříleté okno; quality flag používá konkrétní kategorii a u relativního pravidla posledních pět dřívějších výsledků. Jde o dvě nezávislé vrstvy. Quality flag se v API zobrazuje vedle ML skóre, ale nemění jeho klasifikaci.

## Omezení současného baseline

- Model používá jediný rys a nezohledňuje podmínky závodu, dráhu, počasí ani další kontext, který v uložených výsledcích není.
- Neexistuje zde označená ground-truth sada, metrika přesnosti, train/test rozdělení ani kalibrace skóre mezi různými atlety, skupinami či běhy.
- Výsledky modelu závisí na úplnosti importu, správném párování identity atleta a pevné mapě názvů kategorií.
- `suspicious` quality flag se z ML vstupu nevylučuje; oba signály je nutné interpretovat samostatně.
- Poslední neúplný rok se počítá v okně ukotveném k 31. prosinci, i když jsou v databázi zatím dostupná jen dřívější data daného roku.
- Dotaz vybírající výsledky explicitně nevyžaduje pole `athlete`, ale následné seskupení je očekává. Validní nespárovaný výsledek bez tohoto odkazu proto není bezpečně ošetřen.
- Čištění nečíselných hodnot probíhá uvnitř modelové funkce, zatímco ukládací služba páruje výstupy s původním seznamem podle pořadí. Nestandardní `NaN` nebo nekonečné hodnoty v databázi proto nejsou na úrovni celé pipeline robustně podporované.

Unit testy ověřují minimální počet, čištění ne-konečných hodnot, nízkou varianci, reprodukovatelnost, shodu skóre s negovanou `decision_function` a shodu příznaků s `predict` při `contamination="auto"`.
