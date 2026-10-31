"""
analysis.py - Executable entry point for COGS & Margin Analysis pipeline.
Runs data quality audit, SQL CTE rollups, MEI ranking, sensitivity analysis,
and results generation.
"""

from src.pipeline import run_pipeline

if __name__ == "__main__":
    run_pipeline()
