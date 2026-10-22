[EN](README.md) · **CZ** · [Projekt](../../README.cs.md)

# Průzkumná analýza dat v notebooku

[`eda.ipynb`](eda.ipynb) zkoumá **verzované JSON před importem do MongoDB** pomocí [`docs/analysis`](../analysis). Nečte živou databázi, nesjednocuje kanonické identity a nespouští aplikační Isolation Forest. Nepotřebuje účet, Docker ani tajemství.

## Vstupy, závislosti a pořadí

První buňka hledá kořen projektu podle `docs/` a `data/` v pracovním adresáři či rodičích (nejvýše pět iterací) a přidá jej do `sys.path`. Spouštějte z kořene repozitáře nebo `docs/notebooks/`. Načítání rekurzivně čte seřazené `data/**/*.json`; je třeba úplný checkout včetně analytických helperů.

Notebook importuje pandas, Matplotlib, seaborn a `IPython.display`, dále standardní `pathlib`, `sys` a `json`. Backendové requirements tyto notebookové závislosti neinstalují a **chybí samostatný lockfile notebooku**. Následující příklad přidává nbformat/nbclient/ipykernel pro běh bez UI. Použijte izolované prostředí; projektové závislosti není třeba měnit.

V novém kernelu spusťte všechny buňky shora dolů: nalezení kořene → importy/styl → načtení a zploštění dat → souhrny datasetu/časů → rozdělení/kategorie/IQR odlehlosti → kvalita a možné duplicity → roční/měsíční pokrytí → slovní interpretace. Pozdější buňky používají dřívější proměnné; samostatný běh může selhat nebo zobrazit zastaralý stav.

```bash
# From the repository root / Z kořene repozitáře
python3.12 -m venv /tmp/flamma-eda-venv
. /tmp/flamma-eda-venv/bin/activate
python -m pip install pandas matplotlib seaborn ipython nbformat nbclient ipykernel
python - <<'PYEDA'
from pathlib import Path
import nbformat
from nbclient import NotebookClient
nb = nbformat.read("docs/notebooks/eda.ipynb", as_version=4)
NotebookClient(
    nb, kernel_name="python3", timeout=120,
    resources={"metadata": {"path": str(Path.cwd())}},
).execute()
nbformat.write(nb, "/tmp/flamma-eda.executed.ipynb")
PYEDA
deactivate
```

Výstupní kopie patří do `/tmp`; kvůli obnovení výstupů nepřepisujte verzovaný notebook. Interaktivně jej otevřete v editoru podporujícím Jupyter se stejným prostředím/kernelem. K exportovaným grafům zaznamenejte Git commit, Python a verze balíčků.

## Interpretační omezení

- `athlete_count` počítá unikátní složená jména, nikoli sjednocené identity MongoDB. Varianty týmu/kódu/roku pouze hledají možné duplicity.
- EDA `suspicious_final_time` označuje chybějící čas, nevalidní stav, čas ≥90 s či sentinel 999. **Liší se od** backendových percentilových/historických příznaků i od Isolation Forest.
- Chybějící rok narození EDA hledá pomocí pandas null kontroly; zdrojovou nulu za chybějící nepovažuje. Audit zdrojů samostatně počítá null **i nulu**.
- `valid_results` pro rozdělení navíc vynechává EDA-podezřelé časy; nejde doslova o všechny validní zdrojové řádky.
- Souhrny kategorií seskupují i podle `discipline`; výchozí pandas groupby vynechává null klíče, tedy mohou chybět kategorie bez disciplíny.
- Roční/měsíční pokrytí počítá **všechny řádky `df_results`**, i když některé popisky hovoří o validních výsledcích. Čtěte je jako pokrytí všech zdrojových řádků; notebook byl během dokumentační úpravy zachován.
- Klouzavý průměr pozorovaných měsíců používá tři řádky, nikoli úplnou kalendářní řadu. Chybějící měsíce se automaticky nedoplňují nulou.
- Slovní závěry jsou existující průzkumná tvrzení, nikoli validace na oddělených datech či kauzální závěry. Uložené výstupy nenahrazují opětovné spuštění.

## Stav ověření

Datovaný [audit](../documentation-audit.cs.md) uvádí skutečný výsledek spuštění a verze balíčků. Vstupy a pořadí lze určit, ale bez uzamčeného prostředí a zdrojových extrakčních podkladů nelze slíbit přesnou shodu historických grafů mezi instalacemi. Viz [provenience dat](../data-baseline.md) a odlišný význam [aplikačního ML](../ml-baseline.md).
