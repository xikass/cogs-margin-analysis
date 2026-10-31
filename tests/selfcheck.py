"""
tests/selfcheck.py - Automated integrity test suite for COGS & Margin Analysis.
Asserts:
- 40 products in final database
- >= 100 components in final database
- No negative unit costs after data cleaning
- MEI is finite or properly flagged as negative margin
- break_even_api_price > 0 where margin > 0
- All 6 generated charts exist and are > 10KB
- results.json exists and contains all required keys
- Sensitivity top-10 overlap is bounded in [0, 100]
- Portfolio margin % is in a sane commercial range (20% to 80%)
Exits non-zero on assertion failure.
"""

import sys
import os
import json
import sqlite3
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

def run_tests():
    print("Running automated self-check test suite...")
    db_path = REPO_ROOT / "data" / "cogs.db"
    out_dir = REPO_ROOT / "out"
    charts_dir = REPO_ROOT / "charts"

    # 1. Database assertions
    assert db_path.exists(), f"Database not found at {db_path}"
    conn = sqlite3.connect(db_path)

    df_products = pd.read_sql_query("SELECT * FROM products", conn)
    assert len(df_products) == 40, f"Expected 40 products, got {len(df_products)}"
    print("✓ Assertion passed: 40 products present in database.")

    df_components = pd.read_sql_query("SELECT * FROM components", conn)
    assert len(df_components) >= 100, f"Expected >= 100 components, got {len(df_components)}"
    print(f"✓ Assertion passed: {len(df_components)} components present (>= 100).")

    # No negative costs after cleaning
    neg_costs = df_components[df_components["unit_cost"] < 0]
    assert len(neg_costs) == 0, f"Found {len(neg_costs)} negative unit costs after cleaning"
    print("✓ Assertion passed: Zero negative unit costs after cleaning.")

    # No null costs
    null_costs = df_components[df_components["unit_cost"].isna()]
    assert len(null_costs) == 0, f"Found {len(null_costs)} NULL unit costs after cleaning"
    print("✓ Assertion passed: Zero NULL unit costs after cleaning.")

    # No zero batch sizes
    zero_batches = df_products[df_products["units_per_batch"] <= 0]
    assert len(zero_batches) == 0, f"Found {len(zero_batches)} products with units_per_batch <= 0"
    print("✓ Assertion passed: Zero non-positive batch sizes after cleaning.")

    # No non-positive prices
    bad_prices = df_products[df_products["unit_price"] <= 0]
    assert len(bad_prices) == 0, f"Found {len(bad_prices)} products with unit_price <= 0"
    print("✓ Assertion passed: Zero non-positive unit prices after cleaning.")

    conn.close()

    # 2. Output file assertions
    detail_csv = out_dir / "margin_detail.csv"
    assert detail_csv.exists(), f"margin_detail.csv missing at {detail_csv}"
    df_detail = pd.read_csv(detail_csv)
    assert len(df_detail) == 40, f"Expected 40 SKU detail rows, got {len(df_detail)}"

    # MEI finite or flagged
    for _, r in df_detail.iterrows():
        if r["gross_margin"] <= 0:
            assert r["is_negative_margin"] == 1, f"Product {r['product_id']} has non-positive margin but is_negative_margin != 1"
        else:
            assert pd.notna(r["mei_pct"]) and not pd.isna(r["mei_pct"]), f"Product {r['product_id']} has positive margin but NaN MEI"
            assert r["break_even_api_price"] > 0, f"Product {r['product_id']} has positive margin but break_even_api_price <= 0"
    print("✓ Assertion passed: MEI is finite or flagged, and break_even_api_price > 0 for all profitable SKUs.")

    # 3. Chart file assertions
    expected_charts = [
        "01_cost_waterfall.png",
        "02_tornado.png",
        "03_mei_top10.png",
        "04_margin_vs_mei_scatter.png",
        "05_sector_margin.png",
        "06_breakeven_api.png"
    ]
    for c_name in expected_charts:
        c_path = charts_dir / c_name
        assert c_path.exists(), f"Missing chart {c_name}"
        fsize = c_path.stat().st_size
        assert fsize > 10 * 1024, f"Chart {c_name} size is {fsize} bytes, expected > 10KB"
    print(f"✓ Assertion passed: All {len(expected_charts)} charts exist and exceed 10KB.")

    # 4. results.json assertions
    results_json = out_dir / "results.json"
    assert results_json.exists(), f"results.json missing at {results_json}"
    with open(results_json, "r") as f:
        res = json.load(f)

    required_keys = [
        "portfolio_summary",
        "mei_distribution",
        "sector_breakdown",
        "top_10_mei_skus",
        "top_10_profit_at_risk_skus",
        "rank_stability_sentence"
    ]
    for k in required_keys:
        assert k in res, f"results.json missing key: {k}"

    port_summary = res["portfolio_summary"]
    for pk in ["total_revenue", "total_cogs", "total_gross_margin", "portfolio_gross_margin_pct", "total_profit_at_risk", "portfolio_mei_pct"]:
        assert pk in port_summary, f"portfolio_summary missing key: {pk}"

    gm_pct = port_summary["portfolio_gross_margin_pct"]
    assert 20.0 <= gm_pct <= 80.0, f"Portfolio gross margin {gm_pct}% outside sane range [20, 80]%"
    print(f"✓ Assertion passed: Portfolio gross margin is sane ({gm_pct:.2f}%).")

    # 5. Sensitivity assertions
    sens_csv = out_dir / "sensitivity.csv"
    assert sens_csv.exists(), f"sensitivity.csv missing at {sens_csv}"
    df_sens = pd.read_csv(sens_csv)
    rank_scenarios = df_sens[df_sens["scenario_type"] == "MEI_RANK_STABILITY"]
    for _, r in rank_scenarios.iterrows():
        overlap = r["top_10_overlap_pct"]
        assert 0.0 <= overlap <= 100.0, f"Scenario {r['scenario_name']} overlap {overlap} out of bounds [0, 100]"
        rho = r["spearman_rho"]
        assert -1.0 <= rho <= 1.0, f"Scenario {r['scenario_name']} Spearman rho {rho} out of bounds [-1, 1]"
    print("✓ Assertion passed: Sensitivity top-10 overlap and Spearman rho strictly bounded.")

    print("\nALL 5 TEST SUITES PASSED CLEANLY (100% PASS RATE).")

if __name__ == "__main__":
    try:
        run_tests()
        sys.exit(0)
    except AssertionError as e:
        print(f"TEST FAILED: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}", file=sys.stderr)
        sys.exit(2)
