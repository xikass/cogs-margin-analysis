"""
src/pipeline.py - COGS & Margin Analysis Engine.
Implements:
1. Automated data quality audit and remediation (logging to out/data_quality.csv).
2. Clean SQLite database generation and CTE query execution (sql/cost_rollup.sql, sql/margin_summary.sql).
3. Margin Exposure Index (MEI), profit at risk, and break-even API price calculation.
4. Rank stability sensitivity (±20% API share, ±5pp margin assumptions, Spearman rho).
5. Portfolio sensitivity shocks (±10% API, packaging, FX imported, volume) for tornado visualization.
6. Exports out/margin_detail.csv, out/margin_summary.csv, out/sensitivity.csv, out/results.json.
"""

import os
import json
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parent.parent

def run_data_quality_audit(db_path: str, out_dir: str):
    """
    Audits raw database tables for 6 dirty data failure modes:
    1. Duplicate BOM rows
    2. Orphan BOM rows
    3. Null component unit costs
    4. Negative component unit costs
    5. Zero units per batch
    6. Non-positive unit prices
    Remediates anomalies, saves log to out/data_quality.csv, and writes clean tables to DB.
    """
    os.makedirs(out_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)

    df_products = pd.read_sql_query("SELECT * FROM products", conn)
    df_components = pd.read_sql_query("SELECT * FROM components", conn)
    df_bom = pd.read_sql_query("SELECT * FROM bom_items", conn)
    df_overhead = pd.read_sql_query("SELECT * FROM overhead", conn)

    audit_logs = []

    # 1. Duplicate BOM rows
    dup_mask = df_bom.duplicated(subset=["product_id", "component_id"], keep="first")
    dup_rows = df_bom[dup_mask]
    for _, r in dup_rows.iterrows():
        audit_logs.append({
            "table_name": "bom_items",
            "record_id": f"{r['product_id']}:{r['component_id']}",
            "issue_type": "DUPLICATE_BOM_ROW",
            "raw_value": f"qty={r['qty_per_unit']}, scrap={r['scrap_pct']}%",
            "cleaned_value": "Deduplicated (kept primary entry)",
            "remediation_action": "REMOVED_DUPLICATE"
        })
    df_bom_clean = df_bom[~dup_mask].copy()

    # 2. Orphan BOM rows
    valid_prod_ids = set(df_products["product_id"])
    valid_comp_ids = set(df_components["component_id"])
    orphan_mask = (~df_bom_clean["product_id"].isin(valid_prod_ids)) | (~df_bom_clean["component_id"].isin(valid_comp_ids))
    orphan_rows = df_bom_clean[orphan_mask]
    for _, r in orphan_rows.iterrows():
        audit_logs.append({
            "table_name": "bom_items",
            "record_id": f"{r['product_id']}:{r['component_id']}",
            "issue_type": "ORPHAN_BOM_REFERENCE",
            "raw_value": f"prod={r['product_id']}, comp={r['component_id']}",
            "cleaned_value": "Excluded orphan reference",
            "remediation_action": "PURGED_ORPHAN_ROW"
        })
    df_bom_clean = df_bom_clean[~orphan_mask].copy()

    # 3. Null component unit costs
    null_cost_mask = df_components["unit_cost"].isna()
    null_cost_rows = df_components[null_cost_mask]
    df_components_clean = df_components.copy()
    type_medians = df_components.groupby("type")["unit_cost"].median()
    for _, r in null_cost_rows.iterrows():
        med_val = round(float(type_medians.get(r["type"], 10.0)), 2)
        audit_logs.append({
            "table_name": "components",
            "record_id": str(r["component_id"]),
            "issue_type": "NULL_UNIT_COST",
            "raw_value": "NULL",
            "cleaned_value": f"${med_val:.2f} (type median)",
            "remediation_action": "IMPUTED_MEDIAN"
        })
        df_components_clean.loc[df_components_clean["component_id"] == r["component_id"], "unit_cost"] = med_val

    # 4. Negative component unit costs
    neg_cost_mask = df_components_clean["unit_cost"] < 0
    neg_cost_rows = df_components_clean[neg_cost_mask]
    for _, r in neg_cost_rows.iterrows():
        abs_val = round(abs(float(r["unit_cost"])), 2)
        audit_logs.append({
            "table_name": "components",
            "record_id": str(r["component_id"]),
            "issue_type": "NEGATIVE_UNIT_COST",
            "raw_value": f"${r['unit_cost']:.2f}",
            "cleaned_value": f"${abs_val:.2f} (absolute magnitude)",
            "remediation_action": "RECTIFIED_SIGN"
        })
        df_components_clean.loc[df_components_clean["component_id"] == r["component_id"], "unit_cost"] = abs_val

    # 5. Zero or non-positive units per batch
    zero_batch_mask = df_products["units_per_batch"] <= 0
    zero_batch_rows = df_products[zero_batch_mask]
    df_products_clean = df_products.copy()
    sector_batch_medians = df_products[df_products["units_per_batch"] > 0].groupby("sector")["units_per_batch"].median()
    for _, r in zero_batch_rows.iterrows():
        med_batch = int(sector_batch_medians.get(r["sector"], 10000))
        audit_logs.append({
            "table_name": "products",
            "record_id": str(r["product_id"]),
            "issue_type": "ZERO_BATCH_SIZE",
            "raw_value": f"{r['units_per_batch']}",
            "cleaned_value": f"{med_batch} units (sector median)",
            "remediation_action": "IMPUTED_SECTOR_MEDIAN"
        })
        df_products_clean.loc[df_products_clean["product_id"] == r["product_id"], "units_per_batch"] = med_batch

    # 6. Non-positive unit prices
    bad_price_mask = df_products_clean["unit_price"] <= 0
    bad_price_rows = df_products_clean[bad_price_mask]
    sector_price_medians = df_products_clean[df_products_clean["unit_price"] > 0].groupby("sector")["unit_price"].median()
    for _, r in bad_price_rows.iterrows():
        med_price = round(float(sector_price_medians.get(r["sector"], 20.0)), 2)
        audit_logs.append({
            "table_name": "products",
            "record_id": str(r["product_id"]),
            "issue_type": "NON_POSITIVE_PRICE",
            "raw_value": f"${r['unit_price']:.2f}",
            "cleaned_value": f"${med_price:.2f} (sector median)",
            "remediation_action": "IMPUTED_SECTOR_MEDIAN"
        })
        df_products_clean.loc[df_products_clean["product_id"] == r["product_id"], "unit_price"] = med_price

    # Save audit log
    df_audit = pd.DataFrame(audit_logs)
    audit_csv = os.path.join(out_dir, "data_quality.csv")
    df_audit.to_csv(audit_csv, index=False)

    # Write cleaned tables back to database
    df_products_clean.to_sql("products", conn, if_exists="replace", index=False)
    df_components_clean.to_sql("components", conn, if_exists="replace", index=False)
    df_bom_clean.to_sql("bom_items", conn, if_exists="replace", index=False)
    df_overhead.to_sql("overhead", conn, if_exists="replace", index=False)
    conn.close()

    print(f"Data audit completed: {len(df_audit)} issues detected and remediated. Saved to {audit_csv}.")
    return df_audit


def execute_cost_analysis(db_path: str, sql_dir: str, out_dir: str):
    """
    Executes sql/cost_rollup.sql and sql/margin_summary.sql against SQLite.
    Saves out/margin_detail.csv and out/margin_summary.csv.
    """
    conn = sqlite3.connect(db_path)

    rollup_sql_path = os.path.join(sql_dir, "cost_rollup.sql")
    with open(rollup_sql_path, "r") as f:
        rollup_sql = f.read()

    df_detail = pd.read_sql_query(rollup_sql, conn)
    detail_csv = os.path.join(out_dir, "margin_detail.csv")
    df_detail.to_csv(detail_csv, index=False)

    summary_sql_path = os.path.join(sql_dir, "margin_summary.sql")
    with open(summary_sql_path, "r") as f:
        summary_sql = f.read()

    df_summary = pd.read_sql_query(summary_sql, conn)
    summary_csv = os.path.join(out_dir, "margin_summary.csv")
    df_summary.to_csv(summary_csv, index=False)

    conn.close()
    print(f"Cost analysis executed: {len(df_detail)} SKU rows rolled up, saved to {detail_csv}.")
    return df_detail, df_summary


def run_sensitivity_analysis(df_detail: pd.DataFrame, out_dir: str):
    """
    1. MEI Rank Stability:
       Evaluates rank stability of Margin Exposure Index across 5 scenarios:
       - Baseline
       - API Share +20%
       - API Share -20%
       - Margin Assumption +5pp
       - Margin Assumption -5pp
       Measures top-10 overlap (%) and Spearman rank correlation rho.
    2. Tornado Driver Shocks on Portfolio Gross Margin:
       - API Price +/- 10%
       - Packaging Cost +/- 10%
       - FX on Imported Components +/- 10%
       - Sales Volume +/- 10%
    Saves scenarios in out/sensitivity.csv.
    """
    # Exclude non-positive margin SKUs for MEI rank evaluation
    valid_mask = (df_detail["gross_margin"] > 0) & (df_detail["mei_pct"].notna())
    df_valid = df_detail[valid_mask].copy()

    # Baseline top 10
    baseline_top10 = set(df_valid.sort_values("mei_pct", ascending=False)["product_id"].head(10))
    baseline_ranks = df_valid.set_index("product_id")["mei_pct"].rank(ascending=False)

    scenarios = []

    # Scenario 1: Baseline
    scenarios.append({
        "scenario_type": "MEI_RANK_STABILITY",
        "scenario_name": "Baseline",
        "parameter_adjustment": "None (1.0x API share, baseline margin)",
        "top_10_overlap_pct": 100.0,
        "spearman_rho": 1.0000,
        "portfolio_margin_impact_dollar": 0.0,
        "margin_impact_pp": 0.0
    })

    # Scenario 2: API share +20%
    par_api_high = df_valid["annual_cogs"] * (df_valid["api_share"] * 1.20) * 0.10
    mei_api_high = (par_api_high / df_valid["gross_margin"]) * 100.0
    df_valid["mei_api_high"] = mei_api_high
    top10_api_high = set(df_valid.sort_values("mei_api_high", ascending=False)["product_id"].head(10))
    overlap_api_high = len(baseline_top10.intersection(top10_api_high)) / 10.0 * 100.0
    ranks_api_high = df_valid.set_index("product_id")["mei_api_high"].rank(ascending=False)
    rho_api_high, _ = spearmanr(baseline_ranks, ranks_api_high)

    scenarios.append({
        "scenario_type": "MEI_RANK_STABILITY",
        "scenario_name": "API Share +20%",
        "parameter_adjustment": "API cost share scaled by 1.20x",
        "top_10_overlap_pct": round(overlap_api_high, 1),
        "spearman_rho": round(float(rho_api_high), 4),
        "portfolio_margin_impact_dollar": 0.0,
        "margin_impact_pp": 0.0
    })

    # Scenario 3: API share -20%
    par_api_low = df_valid["annual_cogs"] * (df_valid["api_share"] * 0.80) * 0.10
    mei_api_low = (par_api_low / df_valid["gross_margin"]) * 100.0
    df_valid["mei_api_low"] = mei_api_low
    top10_api_low = set(df_valid.sort_values("mei_api_low", ascending=False)["product_id"].head(10))
    overlap_api_low = len(baseline_top10.intersection(top10_api_low)) / 10.0 * 100.0
    ranks_api_low = df_valid.set_index("product_id")["mei_api_low"].rank(ascending=False)
    rho_api_low, _ = spearmanr(baseline_ranks, ranks_api_low)

    scenarios.append({
        "scenario_type": "MEI_RANK_STABILITY",
        "scenario_name": "API Share -20%",
        "parameter_adjustment": "API cost share scaled by 0.80x",
        "top_10_overlap_pct": round(overlap_api_low, 1),
        "spearman_rho": round(float(rho_api_low), 4),
        "portfolio_margin_impact_dollar": 0.0,
        "margin_impact_pp": 0.0
    })

    # Scenario 4: Margin assumption +5pp
    # Shifting unit margin by +5 percentage points (higher gross margin denominator)
    new_gm_high = df_valid["annual_revenue"] * np.clip((df_valid["gross_margin_pct"] + 5.0) / 100.0, 0.01, 0.99)
    mei_margin_high = (df_valid["profit_at_risk"] / new_gm_high) * 100.0
    df_valid["mei_margin_high"] = mei_margin_high
    top10_margin_high = set(df_valid.sort_values("mei_margin_high", ascending=False)["product_id"].head(10))
    overlap_margin_high = len(baseline_top10.intersection(top10_margin_high)) / 10.0 * 100.0
    ranks_margin_high = df_valid.set_index("product_id")["mei_margin_high"].rank(ascending=False)
    rho_margin_high, _ = spearmanr(baseline_ranks, ranks_margin_high)

    scenarios.append({
        "scenario_type": "MEI_RANK_STABILITY",
        "scenario_name": "Margin Assumption +5pp",
        "parameter_adjustment": "Gross margin percentage increased by +5pp",
        "top_10_overlap_pct": round(overlap_margin_high, 1),
        "spearman_rho": round(float(rho_margin_high), 4),
        "portfolio_margin_impact_dollar": 0.0,
        "margin_impact_pp": 0.0
    })

    # Scenario 5: Margin assumption -5pp
    # Shifting unit margin by -5 percentage points (compressed gross margin denominator)
    new_gm_low = df_valid["annual_revenue"] * np.clip((df_valid["gross_margin_pct"] - 5.0) / 100.0, 0.01, 0.99)
    mei_margin_low = (df_valid["profit_at_risk"] / new_gm_low) * 100.0
    df_valid["mei_margin_low"] = mei_margin_low
    top10_margin_low = set(df_valid.sort_values("mei_margin_low", ascending=False)["product_id"].head(10))
    overlap_margin_low = len(baseline_top10.intersection(top10_margin_low)) / 10.0 * 100.0
    ranks_margin_low = df_valid.set_index("product_id")["mei_margin_low"].rank(ascending=False)
    rho_margin_low, _ = spearmanr(baseline_ranks, ranks_margin_low)

    scenarios.append({
        "scenario_type": "MEI_RANK_STABILITY",
        "scenario_name": "Margin Assumption -5pp",
        "parameter_adjustment": "Gross margin percentage decreased by -5pp",
        "top_10_overlap_pct": round(overlap_margin_low, 1),
        "spearman_rho": round(float(rho_margin_low), 4),
        "portfolio_margin_impact_dollar": 0.0,
        "margin_impact_pp": 0.0
    })

    # Portfolio Baseline
    total_rev = df_detail["annual_revenue"].sum()
    total_cogs = df_detail["annual_cogs"].sum()
    base_gm = total_rev - total_cogs
    base_gm_pct = (base_gm / total_rev) * 100.0

    # Tornado Driver Shocks on Portfolio Gross Margin
    total_annual_api_spend = (df_detail["annual_units"] * df_detail["api_cost_per_unit"]).sum()
    total_annual_pkg_spend = (df_detail["annual_units"] * df_detail["packaging_cost_per_unit"]).sum()
    total_annual_imported_spend = (df_detail["annual_units"] * df_detail["imported_cost_per_unit"]).sum()

    shocks = [
        ("API Price +10%", "TORNADO_SHOCK", "API Price", 0.10, -total_annual_api_spend * 0.10),
        ("API Price -10%", "TORNADO_SHOCK", "API Price", -0.10, total_annual_api_spend * 0.10),
        ("Packaging Cost +10%", "TORNADO_SHOCK", "Packaging Cost", 0.10, -total_annual_pkg_spend * 0.10),
        ("Packaging Cost -10%", "TORNADO_SHOCK", "Packaging Cost", -0.10, total_annual_pkg_spend * 0.10),
        ("FX Imported Components +10%", "TORNADO_SHOCK", "FX Imported", 0.10, -total_annual_imported_spend * 0.10),
        ("FX Imported Components -10%", "TORNADO_SHOCK", "FX Imported", -0.10, total_annual_imported_spend * 0.10),
        ("Sales Volume +10%", "TORNADO_SHOCK", "Sales Volume", 0.10, base_gm * 0.10),
        ("Sales Volume -10%", "TORNADO_SHOCK", "Sales Volume", -0.10, -base_gm * 0.10),
    ]

    for name, s_type, driver, shift, delta_margin in shocks:
        new_gm = base_gm + delta_margin
        new_gm_pct = (new_gm / (total_rev * (1.10 if driver == "Sales Volume" and shift > 0 else (0.90 if driver == "Sales Volume" else 1.0)))) * 100.0
        delta_pp = new_gm_pct - base_gm_pct
        scenarios.append({
            "scenario_type": s_type,
            "scenario_name": name,
            "parameter_adjustment": f"{driver} shifted by {shift:+.1%}",
            "top_10_overlap_pct": np.nan,
            "spearman_rho": np.nan,
            "portfolio_margin_impact_dollar": round(delta_margin, 2),
            "margin_impact_pp": round(delta_pp, 2)
        })

    df_sensitivity = pd.DataFrame(scenarios)
    sens_csv = os.path.join(out_dir, "sensitivity.csv")
    df_sensitivity.to_csv(sens_csv, index=False)
    print(f"Sensitivity analysis completed: saved to {sens_csv}.")

    min_rho = min(rho_api_high, rho_api_low, rho_margin_high, rho_margin_low)
    min_overlap = min(overlap_api_high, overlap_api_low, overlap_margin_high, overlap_margin_low)

    rank_stability_sentence = (
        f"MEI ranking demonstrates strong stability across stress scenarios, maintaining "
        f"{min_overlap:.1f}% to 100.0% top-10 overlap and Spearman rho >= {min_rho:.4f} "
        f"under +/-20% API share and +/-5pp margin shifts."
    )

    return df_sensitivity, rank_stability_sentence


def generate_portfolio_results_json(df_detail: pd.DataFrame, df_summary: pd.DataFrame, rank_sentence: str, out_dir: str):
    """
    Constructs out/results.json with portfolio aggregates, distributions, sector summaries,
    top-10 rankings, and rank stability sentence.
    """
    total_rev = round(float(df_detail["annual_revenue"].sum()), 2)
    total_cogs = round(float(df_detail["annual_cogs"].sum()), 2)
    total_gm = round(total_rev - total_cogs, 2)
    portfolio_gm_pct = round((total_gm / total_rev) * 100.0, 2)
    total_par = round(float(df_detail["profit_at_risk"].sum()), 2)
    portfolio_mei = round((total_par / total_gm) * 100.0, 2)

    valid_mei = df_detail.loc[df_detail["gross_margin"] > 0, "mei_pct"].dropna()

    mei_dist = {
        "count": int(len(valid_mei)),
        "min_mei_pct": round(float(valid_mei.min()), 2),
        "q25_mei_pct": round(float(np.percentile(valid_mei, 25)), 2),
        "median_mei_pct": round(float(np.median(valid_mei)), 2),
        "mean_mei_pct": round(float(np.mean(valid_mei)), 2),
        "q75_mei_pct": round(float(np.percentile(valid_mei, 75)), 2),
        "max_mei_pct": round(float(valid_mei.max()), 2)
    }

    # Top 10 by MEI
    top_10_mei = df_detail.loc[df_detail["gross_margin"] > 0].sort_values("mei_pct", ascending=False).head(10)[
        ["product_id", "product_name", "sector", "unit_price", "unit_cost", "gross_margin_pct", "api_share", "profit_at_risk", "mei_pct", "break_even_api_price"]
    ].to_dict(orient="records")

    # Top 10 by Profit at Risk
    top_10_par = df_detail.sort_values("profit_at_risk", ascending=False).head(10)[
        ["product_id", "product_name", "sector", "annual_revenue", "annual_cogs", "gross_margin", "profit_at_risk", "mei_pct"]
    ].to_dict(orient="records")

    # Sector summary dictionary
    sector_records = df_summary[df_summary["sector"] != "PORTFOLIO"].to_dict(orient="records")

    results_payload = {
        "portfolio_summary": {
            "total_products": int(len(df_detail)),
            "total_annual_units": int(df_detail["annual_units"].sum()),
            "total_revenue": total_rev,
            "total_cogs": total_cogs,
            "total_gross_margin": total_gm,
            "portfolio_gross_margin_pct": portfolio_gm_pct,
            "total_profit_at_risk": total_par,
            "portfolio_mei_pct": portfolio_mei
        },
        "mei_distribution": mei_dist,
        "sector_breakdown": sector_records,
        "top_10_mei_skus": top_10_mei,
        "top_10_profit_at_risk_skus": top_10_par,
        "rank_stability_sentence": rank_sentence
    }

    out_file = os.path.join(out_dir, "results.json")
    with open(out_file, "w") as f:
        json.dump(results_payload, f, indent=2)

    print(f"Results summary JSON generated: saved to {out_file}.")
    return results_payload


def run_pipeline():
    db_path = str(REPO_ROOT / "data" / "cogs.db")
    sql_dir = str(REPO_ROOT / "sql")
    out_dir = str(REPO_ROOT / "out")

    # 1. Audit & Clean Data
    run_data_quality_audit(db_path, out_dir)

    # 2. Execute SQL & Calculate Margins
    df_detail, df_summary = execute_cost_analysis(db_path, sql_dir, out_dir)

    # 3. Sensitivity Analysis
    df_sens, rank_sentence = run_sensitivity_analysis(df_detail, out_dir)

    # 4. JSON Summary
    generate_portfolio_results_json(df_detail, df_summary, rank_sentence, out_dir)

if __name__ == "__main__":
    run_pipeline()
