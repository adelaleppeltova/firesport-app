"""Analyzátor trendů výkonu atleta."""
from typing import List
from ml.tasks.regression.linear_regression import linear_regression, calculate_r_squared
from app.models.athlete import PerformanceTrend, RecentResult


def analyze_performance_trend(times: List[float]) -> PerformanceTrend:
    """
    Analyzuje trend výkonu atleta pomocí lineární regrese.
    
    Menší čas = lepší výkon.
    
    Args:
        times: Seznam časů z posloupných závodů
        
    Returns:
        PerformanceTrend: improving, declining, nebo stable
    """
    if len(times) < 2:
        return PerformanceTrend.stable
    
    try:
        slope, _ = linear_regression(times)
        
        # Prahová hodnota pro stabilitu (sekund)
        threshold = 0.5
        
        if abs(slope) < threshold:
            return PerformanceTrend.stable
        elif slope < 0:
            # Sklon < 0 znamená klesající časy = zlepšení
            return PerformanceTrend.improving
        else:
            # Sklon > 0 znamená rostoucí časy = zhoršení
            return PerformanceTrend.declining
    except Exception:
        return PerformanceTrend.stable


def get_recent_results_from_times(times: List[float], ranks: List[int]) -> List[RecentResult]:
    """
    Vrátí posledních 5 výsledků s časy a pořadím.
    
    Args:
        times: Seřazené časy (nejstarší první)
        ranks: Seřazená pořadí
        
    Returns:
        List[RecentResult]: Posledních 5 výsledků
    """
    recent = []
    for i in range(min(5, len(times))):
        recent.append(RecentResult(
            final_time=times[i] if i < len(times) else None,
            rank=ranks[i] if i < len(ranks) else None
        ))
    return recent


def get_trend_stats(times: List[float]) -> dict:
    """
    Vrátí statistiku trendu.
    
    Returns:
        dict: slope, intercept, r_squared, trend
    """
    if len(times) < 2:
        return {
            "slope": 0.0,
            "intercept": 0.0,
            "r_squared": 0.0,
            "trend": PerformanceTrend.stable
        }
    
    slope, intercept = linear_regression(times)
    r_squared = calculate_r_squared(times)
    trend = analyze_performance_trend(times)
    
    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "trend": trend
    }
