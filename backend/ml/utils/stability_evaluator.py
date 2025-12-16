"""Hodnocení a interpretace stability výkonu."""
from typing import List
from ml.tasks.stability.stability_analyzer import (
    calculate_performance_consistency,
    get_stability_stats
)


def get_stability_rating(times: List[float]) -> str:
    """
    Vrátí slovní hodnocení stability výkonu.
    
    Args:
        times: Seznam časů z aktuálního roku
        
    Returns:
        str: Slovní hodnocení (velmi vysoká, vysoká, průměrná, nízká, velmi nízká)
    """
    if len(times) < 2:
        return "Nedostatek dat"
    
    consistency = calculate_performance_consistency(times)
    
    if consistency >= 0.9:
        return "Velmi vysoká stabilita"
    elif consistency >= 0.75:
        return "Vysoká stabilita"
    elif consistency >= 0.6:
        return "Průměrná stabilita"
    elif consistency >= 0.4:
        return "Nízká stabilita"
    else:
        return "Velmi nízká stabilita"


def get_stability_description(times: List[float]) -> str:
    """
    Vrátí detailnější popis stability.
    
    Returns:
        str: Popis se doporučením
    """
    if len(times) < 2:
        return "Nedostatek dat pro analýzu stability."
    
    consistency = calculate_performance_consistency(times)
    stats = get_stability_stats(times)
    
    cv = stats["cv"]
    std_dev = stats["std_dev"]
    mean = stats["mean"]
    
    desc = f"Koeficient variace: {cv:.1f}%. "
    
    if consistency >= 0.9:
        desc += "Tvůj výkon je extrémně stabilní! 🎯"
    elif consistency >= 0.75:
        desc += "Tvůj výkon je velmi konzistentní. Počítej na svou spolehlivost. ✓"
    elif consistency >= 0.6:
        desc += "Tvůj výkon je přijatelně stabilní, ale jsou chvíle kolísání."
    elif consistency >= 0.4:
        desc += "Tvůj výkon kolísá. Pracuj na konzistentnosti."
    else:
        desc += "Tvůj výkon je velmi variabilní. Zaměř se na stabilizaci."
    
    return desc


def get_stability_analysis(times: List[float]) -> dict:
    """
    Vrátí komplexní analýzu stability.
    
    Returns:
        dict: rating, description, stats
    """
    return {
        "rating": get_stability_rating(times),
        "description": get_stability_description(times),
        "stats": get_stability_stats(times),
        "consistency_score": calculate_performance_consistency(times)  # 0-1
    }
