"""Simple helpers for exploratory analysis of extracted competition JSON files."""

from .loaders import load_json_file, load_json_files_from_dir
from .queries import (
    filter_results_by_discipline,
    get_categories,
    get_competitions,
    get_results,
)
from .transforms import (
    add_quality_flags,
    competitions_to_dataframe,
    find_inconsistent_team_names,
    find_missing_attempts,
    find_possible_duplicate_athletes,
    results_to_dataframe,
    summarize_data_quality,
    summarize_dataset,
    summarize_final_times,
)

__all__ = [
    "add_quality_flags",
    "competitions_to_dataframe",
    "filter_results_by_discipline",
    "find_inconsistent_team_names",
    "find_missing_attempts",
    "find_possible_duplicate_athletes",
    "get_categories",
    "get_competitions",
    "get_results",
    "load_json_file",
    "load_json_files_from_dir",
    "results_to_dataframe",
    "summarize_data_quality",
    "summarize_dataset",
    "summarize_final_times",
]
