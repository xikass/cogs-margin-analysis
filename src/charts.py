"""
src/charts.py - Decision-grade visualizations for COGS & Margin Analysis.
Generates 6 colorblind-safe, publication-ready charts (150 DPI):
1. 01_cost_waterfall.png - Portfolio cost-driver waterfall (Revenue to Gross Margin)
2. 02_tornado.png - Tornado chart of +/-10% drivers on gross margin
3. 03_mei_top10.png - MEI top-10 bar chart colored by sector with margin % annotations
4. 04_margin_vs_mei_scatter.png - Margin % vs MEI scatter (bubble=revenue, median quadrants)
5. 05_sector_margin.png - Sector comparison of Revenue, COGS, Gross Margin, and Margin %
6. 06_breakeven_api.png - Break-even vs current API price dumbbell plot for top exposed SKUs
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

REPO_ROOT = Path(__file__).resolve().parent.parent

# Colorblind-safe palette (Wong / Okabe-Ito inspired)
SECTOR_COLORS = {
    "COSMETICS": "#e69f00",       # Orange
    "HUMAN_PHARMA": "#0072b2",    # Deep Blue
    "VETERINARY": "#009e73",      # Bluish Green
    "FOOD_SUPPLEMENT": "#cc79a7"  # Reddish Purple
}

def set_style():
    plt.rcParams.update({
        "font.sans-serif": "DejaVu Sans",
        "font.family": "sans-serif",
        "figure.titlesize": 14,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.autolayout": True,
        "axes.edgecolor": "#cccccc",
        "axes.linewidth": 0.8,
        "grid.color": "#ebebeb",
        "grid.linestyle": "--",
        "grid.linewidth": 0.6
    })

def generate_waterfall_chart(df_detail: pd.DataFrame, out_path: str):
    """
    1. Portfolio cost-driver waterfall:
    Revenue -> API -> Excipients -> Packaging -> Labor -> Overhead -> Gross Margin
    """
    set_style()
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

    total_rev = df_detail["annual_revenue"].sum() / 1e6
    total_api = (df_detail["annual_units"] * df_detail["api_cost_per_unit"]).sum() / 1e6
    total_exc = (df_detail["annual_units"] * df_detail["excipient_cost_per_unit"]).sum() / 1e6
    total_pkg = (df_detail["annual_units"] * df_detail["packaging_cost_per_unit"]).sum() / 1e6
    total_lab = (df_detail["annual_units"] * df_detail["labor_cost_per_unit"]).sum() / 1e6
    total_ovh = (df_detail["annual_units"] * df_detail["overhead_cost_per_unit"]).sum() / 1e6
    total_gm = df_detail["gross_margin"].sum() / 1e6

    steps = [
        ("Gross Revenue", total_rev, 0.0, True),
        ("Active (API)", -total_api, total_rev - total_api, False),
        ("Excipients", -total_exc, total_rev - total_api - total_exc, False),
        ("Packaging", -total_pkg, total_rev - total_api - total_exc - total_pkg, False),
        ("Direct Labor", -total_lab, total_rev - total_api - total_exc - total_pkg - total_lab, False),
        ("Plant Overhead", -total_ovh, total_gm, False),
        ("Gross Margin", total_gm, 0.0, True)
    ]

    names = [s[0] for s in steps]
    x_pos = np.arange(len(steps))

    for i, (name, val, bottom, is_total) in enumerate(steps):
        if is_total:
            color = "#0072b2" if "Revenue" in name else "#009e73"
            ax.bar(i, val, bottom=bottom, color=color, width=0.55, edgecolor="#333333", linewidth=0.8, zorder=3)
            ax.text(i, val + 1.2, f"${val:.1f}M", ha="center", va="bottom", fontweight="bold", fontsize=10)
        else:
            color = "#d55e00"
            bar_bottom = bottom
            ax.bar(i, abs(val), bottom=bar_bottom, color=color, width=0.55, edgecolor="#333333", linewidth=0.8, zorder=3)
            ax.text(i, bar_bottom + abs(val)/2.0, f"-${abs(val):.1f}M", ha="center", va="center", color="white", fontweight="bold", fontsize=9)

        # Connector line
        if i < len(steps) - 1:
            line_y = total_rev if i == 0 else bottom
            ax.plot([i + 0.275, i + 1 - 0.275], [line_y, line_y], color="#666666", linestyle=":", linewidth=1.2, zorder=2)

    ax.set_xticks(x_pos)
    ax.set_xticklabels(names, rotation=15, ha="right", fontweight="semibold")
    ax.set_ylabel("Portfolio Value ($ Millions USD)", fontweight="semibold")
    ax.set_title("Enterprise Cost-Driver Waterfall: Gross Revenue to Gross Margin", fontweight="bold", pad=14)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("$%.0fM"))
    ax.grid(axis="y", zorder=0)
    ax.set_ylim(0, total_rev * 1.12)

    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {out_path}")

def generate_tornado_chart(df_detail: pd.DataFrame, out_path: str):
    """
    2. Tornado chart of +/-10% drivers on portfolio gross margin.
    """
    set_style()
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)

    total_rev = df_detail["annual_revenue"].sum()
    total_cogs = df_detail["annual_cogs"].sum()
    base_gm = total_rev - total_cogs

    total_api = (df_detail["annual_units"] * df_detail["api_cost_per_unit"]).sum()
    total_pkg = (df_detail["annual_units"] * df_detail["packaging_cost_per_unit"]).sum()
    total_imp = (df_detail["annual_units"] * df_detail["imported_cost_per_unit"]).sum()

    drivers = [
        {"name": "Sales Volume (+/-10%)", "down": -base_gm * 0.10 / 1e6, "up": base_gm * 0.10 / 1e6},
        {"name": "API Price (+/-10%)", "down": -total_api * 0.10 / 1e6, "up": total_api * 0.10 / 1e6},
        {"name": "FX on Imported (+/-10%)", "down": -total_imp * 0.10 / 1e6, "up": total_imp * 0.10 / 1e6},
        {"name": "Packaging Cost (+/-10%)", "down": -total_pkg * 0.10 / 1e6, "up": total_pkg * 0.10 / 1e6}
    ]

    # Sort by maximum absolute swing
    drivers.sort(key=lambda d: abs(d["up"]), reverse=False)

    y_pos = np.arange(len(drivers))
    names = [d["name"] for d in drivers]
    down_vals = [d["down"] for d in drivers]
    up_vals = [d["up"] for d in drivers]

    ax.barh(y_pos, down_vals, height=0.45, color="#d55e00", label="Adverse Impact (-$M)", zorder=3)
    ax.barh(y_pos, up_vals, height=0.45, color="#009e73", label="Favorable Impact (+$M)", zorder=3)

    # Annotations
    for i, d in enumerate(drivers):
        ax.text(d["down"] - 0.2, i, f"-${abs(d['down']):.2f}M", va="center", ha="right", fontsize=9, fontweight="bold", color="#d55e00")
        ax.text(d["up"] + 0.2, i, f"+${abs(d['up']):.2f}M", va="center", ha="left", fontsize=9, fontweight="bold", color="#009e73")

    ax.axvline(0, color="#333333", linewidth=1.0, linestyle="-", zorder=4)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontweight="semibold")
    ax.set_xlabel("Gross Margin Impact ($ Millions USD)", fontweight="semibold")
    ax.set_title("Sensitivity Tornado: Impact of +/-10% Operational Shocks on Gross Margin", fontweight="bold", pad=14)
    ax.legend(loc="lower right", frameon=True)
    ax.grid(axis="x", zorder=0)

    max_range = max(abs(min(down_vals)), max(up_vals)) * 1.35
    ax.set_xlim(-max_range, max_range)
    ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("$%+.1fM"))

    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {out_path}")

def generate_mei_top10_chart(df_detail: pd.DataFrame, out_path: str):
    """
    3. MEI top-10 bar chart colored by sector with margin % annotations.
    """
    set_style()
    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=150)

    top10 = df_detail.loc[df_detail["gross_margin"] > 0].sort_values("mei_pct", ascending=True).tail(10)

    y_pos = np.arange(len(top10))
    colors = [SECTOR_COLORS.get(sec, "#666666") for sec in top10["sector"]]

    bars = ax.barh(y_pos, top10["mei_pct"], height=0.55, color=colors, edgecolor="#333333", linewidth=0.6, zorder=3)

    for i, (_, row) in enumerate(top10.iterrows()):
        val = row["mei_pct"]
        gm_pct = row["gross_margin_pct"]
        ax.text(val + 0.6, i, f"MEI: {val:.1f}%  (GM: {gm_pct:.1f}%)", va="center", ha="left", fontsize=9, fontweight="bold")

    ax.set_yticks(y_pos)
    labels = [f"{r['product_id']}: {r['product_name'][:25]}" for _, r in top10.iterrows()]
    ax.set_yticklabels(labels, fontsize=9.5)
    ax.set_xlabel("Margin Exposure Index (MEI %: Profit at Risk / Gross Margin)", fontweight="semibold")
    ax.set_title("Top 10 Most Vulnerable SKUs by Margin Exposure Index (MEI)", fontweight="bold", pad=14)
    ax.grid(axis="x", zorder=0)
    ax.set_xlim(0, max(top10["mei_pct"]) * 1.35)

    # Sector Legend
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=color, edgecolor="#333333", label=sec.replace("_", " ")) for sec, color in SECTOR_COLORS.items()]
    ax.legend(handles=legend_elements, title="Sector", loc="lower right", frameon=True)

    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {out_path}")

def generate_margin_vs_mei_scatter(df_detail: pd.DataFrame, out_path: str):
    """
    4. Margin % vs MEI scatter:
    Bubble size = Annual Revenue, quadrant lines at medians.
    """
    set_style()
    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=150)

    valid = df_detail.loc[df_detail["gross_margin"] > 0].copy()

    med_margin = valid["gross_margin_pct"].median()
    med_mei = valid["mei_pct"].median()

    # Normalize bubble size
    min_rev, max_rev = valid["annual_revenue"].min(), valid["annual_revenue"].max()
    sizes = 80 + (valid["annual_revenue"] - min_rev) / (max_rev - min_rev) * 450

    for sector, group in valid.groupby("sector"):
        color = SECTOR_COLORS.get(sector, "#666666")
        ax.scatter(
            group["gross_margin_pct"],
            group["mei_pct"],
            s=sizes.loc[group.index],
            color=color,
            alpha=0.75,
            edgecolors="#333333",
            linewidth=0.8,
            label=sector.replace("_", " "),
            zorder=3
        )

    # Quadrant lines
    ax.axvline(med_margin, color="#777777", linestyle="--", linewidth=1.1, zorder=2)
    ax.axhline(med_mei, color="#777777", linestyle="--", linewidth=1.1, zorder=2)

    # Annotate high exposure outlier
    outlier = valid.loc[valid["mei_pct"].idxmax()]
    ax.annotate(
        f"{outlier['product_id']} ({outlier['product_name'][:18]})\nMEI: {outlier['mei_pct']:.1f}%, GM: {outlier['gross_margin_pct']:.1f}%",
        xy=(outlier["gross_margin_pct"], outlier["mei_pct"]),
        xytext=(outlier["gross_margin_pct"] + 4, outlier["mei_pct"] - 4),
        arrowprops=dict(facecolor="#333333", shrink=0.08, width=1, headwidth=6),
        fontsize=8.5,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff2ae", edgecolor="#ccaa00", alpha=0.9)
    )

    # Quadrant labels
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    ax.text(x_max - 2, y_max - 2, "High Margin / High MEI\n(API-Intensive Growth)", ha="right", va="top", fontsize=8.5, style="italic", color="#555555")
    ax.text(x_min + 2, y_max - 2, "Low Margin / High MEI\n(CRITICAL RISK ZONE)", ha="left", va="top", fontsize=8.5, style="italic", color="#cc0000", fontweight="bold")
    ax.text(x_max - 2, y_min + 1, "High Margin / Low MEI\n(Resilient Cash Cows)", ha="right", va="bottom", fontsize=8.5, style="italic", color="#007700", fontweight="bold")
    ax.text(x_min + 2, y_min + 1, "Low Margin / Low MEI\n(Commodity Buffer)", ha="left", va="bottom", fontsize=8.5, style="italic", color="#555555")

    ax.set_xlabel("Gross Margin Percentage (GM %)", fontweight="semibold")
    ax.set_ylabel("Margin Exposure Index (MEI %)", fontweight="semibold")
    ax.set_title("Portfolio Risk Matrix: Gross Margin % vs Margin Exposure Index (MEI)", fontweight="bold", pad=14)
    ax.legend(title="Sector", loc="upper right", frameon=True)
    ax.grid(True, zorder=0)

    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {out_path}")

def generate_sector_margin_chart(df_summary: pd.DataFrame, out_path: str):
    """
    5. Sector margin comparison bar chart (Revenue, COGS, Gross Margin).
    """
    set_style()
    fig, ax1 = plt.subplots(figsize=(10, 6), dpi=150)

    sec_df = df_summary[df_summary["sector"] != "PORTFOLIO"].copy()
    sectors = [s.replace("_", "\n") for s in sec_df["sector"]]

    x = np.arange(len(sectors))
    width = 0.25

    rev = sec_df["total_revenue"] / 1e6
    cogs = sec_df["total_cogs"] / 1e6
    gm = sec_df["total_gross_margin"] / 1e6
    gm_pct = sec_df["gross_margin_pct"]

    rects1 = ax1.bar(x - width, rev, width, label="Revenue", color="#0072b2", edgecolor="#333333", linewidth=0.7, zorder=3)
    rects2 = ax1.bar(x, cogs, width, label="COGS", color="#d55e00", edgecolor="#333333", linewidth=0.7, zorder=3)
    rects3 = ax1.bar(x + width, gm, width, label="Gross Margin", color="#009e73", edgecolor="#333333", linewidth=0.7, zorder=3)

    ax1.set_ylabel("Financials ($ Millions USD)", fontweight="semibold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(sectors, fontweight="semibold")
    ax1.yaxis.set_major_formatter(ticker.FormatStrFormatter("$%.0fM"))
    ax1.grid(axis="y", zorder=0)

    # Annotate margin percentage
    for i in range(len(sectors)):
        ax1.text(x[i] + width, gm.iloc[i] + 0.6, f"{gm_pct.iloc[i]:.1f}%\nMargin", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#006644")

    ax1.set_title("Manufacturing Sector Financials & Margin Performance Comparison", fontweight="bold", pad=14)
    ax1.legend(loc="upper left", frameon=True)
    ax1.set_ylim(0, max(rev) * 1.25)

    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {out_path}")

def generate_breakeven_api_chart(df_detail: pd.DataFrame, out_path: str):
    """
    6. Break-even API price vs current API price (top-15 SKUs dumbbell plot).
    """
    set_style()
    fig, ax = plt.subplots(figsize=(11, 7.5), dpi=150)

    # Top 15 SKUs by MEI
    top15 = df_detail.loc[(df_detail["gross_margin"] > 0) & (df_detail["break_even_api_price"].notna())].sort_values("mei_pct", ascending=True).tail(15)

    y_pos = np.arange(len(top15))
    current_prices = top15["current_api_price"].values
    be_prices = top15["break_even_api_price"].values

    # Connecting horizontal line (runway)
    for i in range(len(top15)):
        ax.plot([current_prices[i], be_prices[i]], [i, i], color="#888888", linewidth=2.2, zorder=2)
        headroom_pct = ((be_prices[i] - current_prices[i]) / current_prices[i]) * 100.0
        mid_x = (current_prices[i] + be_prices[i]) / 2.0
        ax.text(be_prices[i] + 12, i, f"${be_prices[i]:.0f} (+{headroom_pct:.0f}%)", va="center", ha="left", fontsize=8.5, fontweight="bold", color="#d55e00")

    # Current Price dots
    ax.scatter(current_prices, y_pos, color="#0072b2", s=75, zorder=3, label="Current API Price ($/kg)", edgecolors="#333333")
    # Break-even Price dots
    ax.scatter(be_prices, y_pos, color="#d55e00", s=75, zorder=3, label="Break-Even API Price ($/kg)", edgecolors="#333333")

    labels = [f"{r['product_id']}: {r['product_name'][:24]}" for _, r in top15.iterrows()]
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("API Price ($ USD per kg)", fontweight="semibold")
    ax.set_title("API Price Break-Even Headroom Analysis (Top 15 Vulnerable SKUs)", fontweight="bold", pad=14)
    ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("$%.0f"))
    ax.grid(axis="x", zorder=0)
    ax.set_xlim(0, max(be_prices) * 1.25)
    ax.legend(loc="lower right", frameon=True)

    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {out_path}")

def generate_all_charts():
    detail_csv = REPO_ROOT / "out" / "margin_detail.csv"
    summary_csv = REPO_ROOT / "out" / "margin_summary.csv"
    charts_dir = REPO_ROOT / "charts"
    os.makedirs(charts_dir, exist_ok=True)

    df_detail = pd.read_csv(detail_csv)
    df_summary = pd.read_csv(summary_csv)

    generate_waterfall_chart(df_detail, str(charts_dir / "01_cost_waterfall.png"))
    generate_tornado_chart(df_detail, str(charts_dir / "02_tornado.png"))
    generate_mei_top10_chart(df_detail, str(charts_dir / "03_mei_top10.png"))
    generate_margin_vs_mei_scatter(df_detail, str(charts_dir / "04_margin_vs_mei_scatter.png"))
    generate_sector_margin_chart(df_summary, str(charts_dir / "05_sector_margin.png"))
    generate_breakeven_api_chart(df_detail, str(charts_dir / "06_breakeven_api.png"))

if __name__ == "__main__":
    generate_all_charts()
