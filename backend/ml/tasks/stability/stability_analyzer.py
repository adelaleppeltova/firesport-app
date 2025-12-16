"""Analýza variability a stability výkonu."""
import numpy as np
from typing import List, Tuple


def calculate_variance(times: List[float]) -> float:
    """
    Vypočítá rozptyl (variance) časů.
    
    Args:
        times: Seznam časů
        
    Returns:
        float: Rozptyl (variance)
    """
    if len(times) < 2:
        return 0.0
    
    try:
        return float(np.var(times))
    except (ValueError, TypeError):
        return 0.0


def calculate_standard_deviation(times: List[float]) -> float:
    """
    Vypočítá standardní odchylku časů.
    
    Args:
        times: Seznam časů
        
    Returns:
        float: Standardní odchylka
    """
    if len(times) < 2:
        return 0.0
    
    try:
        return float(np.std(times))
    except (ValueError, TypeError):
        return 0.0


def calculate_coefficient_of_variation(times: List[float]) -> float:
    """
    Vypočítá koeficient variace (CV) - relativní rozptyl.
    
    CV = (Standardní odchylka / Průměr) * 100 %
    
    Args:
        times: Seznam časů
        
    Returns:
        float: Koeficient variace v procentech (0-100)
    """
    if len(times) < 2:
        return 0.0
    
    try:
        mean = np.mean(times)
        if mean == 0:
            return 0.0
        
        std = np.std(times)
        cv = (std / mean) * 100
        return float(cv)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0


def calculate_performance_consistency(times: List[float]) -> float:
    """
    Vypočítá konzistenci výkonu (inverzní hodnota CV).
    
    1 - (CV / 100) poskytuje hodnotu kde:
    - 1.0 = perfektně konzistentní
    - 0.5 = průměrně konzistentní
    - 0.0 = velmi nekonzistentní
    
    Args:
        times: Seznam časů
        
    Returns:
        float: Konzistence (0-1)
    """
    cv = calculate_coefficient_of_variation(times)
    consistency = max(0.0, 1.0 - (cv / 100.0))
    return float(consistency)


def calculate_range(times: List[float]) -> float:
    """
    Vypočítá rozpětí (max - min).
    
    Args:
        times: seznam časů
        
    Returns:
        float: Rozpětí
    """
    if len(times) < 2:
        return 0.0
    
    try:
        return float(np.max(times) - np.min(times))
    except (ValueError, TypeError):
        return 0.0


def get_stability_stats(times: List[float]) -> dict:
    """
    Vrátí komplexní statistiku stability.
    
    Returns:
        dict: variance, std_dev, cv, consistency, range, mean
    """
    if len(times) < 2:
        return {
            "variance": 0.0,
            "std_dev": 0.0,
            "cv": 0.0,
            "consistency": 1.0,
            "range": 0.0,
            "mean": 0.0
        }
    
    try:
        times_array = np.array(times, dtype=float)
        return {
            "variance": float(np.var(times_array)),
            "std_dev": float(np.std(times_array)),
            "cv": calculate_coefficient_of_variation(times),
            "consistency": calculate_performance_consistency(times),
            "range": float(np.max(times_array) - np.min(times_array)),
            "mean": float(np.mean(times_array))
        }
    except (ValueError, TypeError):
        return {
            "variance": 0.0,
            "std_dev": 0.0,
            "cv": 0.0,
            "consistency": 1.0,
            "range": 0.0,
            "mean": 0.0
        }
