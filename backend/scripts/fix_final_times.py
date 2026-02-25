#!/usr/bin/env python3
"""
Skript pro opravu final_time a final_status v JSON souborech.
Nastaví final_time na nejnižší validní čas z pole times a final_status na 'valid'.
Pokud žádný validní čas není, nastaví final_time na None a final_status na 'missing'.

Použití:
    python backend/scripts/fix_final_times.py path/to/file.json
    python backend/scripts/fix_final_times.py path/to/file1.json path/to/file2.json ...
"""

import json
import sys
from pathlib import Path


def fix_final_times_in_file(file_path: str) -> int:
    """
    Opraví final_time a final_status v daném JSON souboru.
    
    Returns:
        Počet opravených výsledků
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"✗ Soubor {file_path} neexistuje")
        return 0
    
    if not file_path.suffix == '.json':
        print(f"✗ Soubor {file_path} není JSON")
        return 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"✗ Chyba při parsování {file_path}: {e}")
        return 0
    except Exception as e:
        print(f"✗ Chyba při čtení {file_path}: {e}")
        return 0
    
    fixed_count = 0
    
    # Projdi všechny kategorie a výsledky
    for category in data.get("competition", {}).get("categories", []):
        for result in category.get("results", []):
            # Najdi všechny validní časy
            valid_times = [
                t.get("time")
                for t in result.get("times", [])
                if t.get("status") == "valid" and t.get("time") is not None
            ]
            
            if valid_times:
                # Vezmi nejnižší validní čas
                min_time = min(valid_times)
                result["final_time"] = min_time
                result["final_status"] = "valid"
            else:
                # Pokud žádný validní čas není, nech null a missing
                result["final_time"] = None
                result["final_status"] = "missing"
            
            fixed_count += 1
    
    # Ulož zpět
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ {file_path}: opraveno {fixed_count} výsledků")
        return fixed_count
    except Exception as e:
        print(f"✗ Chyba při zápisu {file_path}: {e}")
        return 0


def main():
    if len(sys.argv) < 2:
        print("Použití: python fix_final_times.py <cesta_k_souboru> [soubor2.json ...]")
        print("\nPříklad:")
        print("  python fix_final_times.py data/2023/skutec/dorostenci_2023.json")
        print("  python fix_final_times.py data/2023/skutec/*.json")
        sys.exit(1)
    
    total_fixed = 0
    
    for file_path in sys.argv[1:]:
        total_fixed += fix_final_times_in_file(file_path)
    
    print(f"\nCelkem opraveno výsledků: {total_fixed}")


if __name__ == "__main__":
    main()
