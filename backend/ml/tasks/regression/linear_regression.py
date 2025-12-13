"""Lineární regrese pro analýzu trendů výkonu."""
import numpy as np
from typing import List, Tuple


def linear_regression(times: List[float]) -> Tuple[float, float]:
    """
    Vypočítá lineární regresi pomocí metody nejmenších čtverců.
    
    Args:
        times: Seznam časů (čím menší, tím lepší)
        
    Returns:
        Tuple (slope, intercept) - sklon a posun přímky
        Sklon > 0: časy se zvyšují (zhoršení)
        Sklon < 0: časy se snižují (zlepšení)
        Sklon ≈ 0: stabilní výkon
    """
    if len(times) < 2:
        return 0.0, 0.0
    
    try:
        x = np.arange(len(times))  # Pozice v čase
        y = np.array(times, dtype=float)  # Časy
        
        # Lineární regrese: y = slope * x + intercept
        coefficients = np.polyfit(x, y, 1)
        slope = float(coefficients[0])
        intercept = float(coefficients[1])
        
        return slope, intercept
    except (ValueError, TypeError):
        return 0.0, 0.0


def calculate_r_squared(times: List[float]) -> float:
    """
    Vypočítá R² (koeficient determinace) pro kvalitu regrese.
    
    Returns:
        float: R² hodnota v rozmezí [0, 1]
        1.0 = perfektní fit
        0.0 = žádná lineární vazba
    """
    if len(times) < 2:
        return 0.0
    
    try:
        x = np.arange(len(times))
        y = np.array(times, dtype=float)
        
        # Vypočítej předpovídané hodnoty
        coefficients = np.polyfit(x, y, 1)
        y_pred = coefficients[0] * x + coefficients[1]
        
        # SS_res (suma čtvercových reziduí)
        ss_res = np.sum((y - y_pred) ** 2)
        # SS_tot (celková suma čtverců)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        
        if ss_tot == 0:
            return 0.0
        
        r_squared = 1 - (ss_res / ss_tot)
        return float(max(0.0, r_squared))  # Zajistí minimálně 0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0
