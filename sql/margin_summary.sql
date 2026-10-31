-- sql/margin_summary.sql
-- Aggregated COGS, margin, and Margin Exposure Index (MEI) by sector and portfolio

WITH component_unit_costs AS (
    SELECT
        b.product_id,
        b.component_id,
        c.type AS component_type,
        c.is_imported,
        (b.qty_per_unit * (1.0 + b.scrap_pct / 100.0) * c.unit_cost) AS effective_cost_per_unit
    FROM bom_items b
    JOIN components c ON b.component_id = c.component_id
),
component_rollups AS (
    SELECT
        product_id,
        SUM(CASE WHEN component_type = 'API' THEN effective_cost_per_unit ELSE 0.0 END) AS api_cost_per_unit,
        SUM(effective_cost_per_unit) AS direct_material_cost
    FROM component_unit_costs
    GROUP BY product_id
),
sku_margins AS (
    SELECT
        p.product_id,
        p.sector,
        p.annual_units,
        p.unit_price,
        (p.annual_units * p.unit_price) AS annual_revenue,
        (p.annual_units * (cr.direct_material_cost + ((o.labor_per_batch + o.overhead_per_batch) * 1.0 / p.units_per_batch))) AS annual_cogs,
        ((p.annual_units * p.unit_price) - (p.annual_units * (cr.direct_material_cost + ((o.labor_per_batch + o.overhead_per_batch) * 1.0 / p.units_per_batch)))) AS gross_margin,
        (p.annual_units * cr.api_cost_per_unit * 0.10) AS profit_at_risk
    FROM products p
    JOIN component_rollups cr ON p.product_id = cr.product_id
    JOIN overhead o ON p.product_id = o.product_id
),
sector_summary AS (
    SELECT
        sector,
        COUNT(product_id) AS sku_count,
        SUM(annual_units) AS total_units,
        SUM(annual_revenue) AS total_revenue,
        SUM(annual_cogs) AS total_cogs,
        SUM(gross_margin) AS total_gross_margin,
        (SUM(gross_margin) * 100.0 / SUM(annual_revenue)) AS gross_margin_pct,
        SUM(profit_at_risk) AS total_profit_at_risk,
        (SUM(profit_at_risk) * 100.0 / SUM(gross_margin)) AS sector_mei_pct
    FROM sku_margins
    GROUP BY sector
),
portfolio_total AS (
    SELECT
        'PORTFOLIO' AS sector,
        COUNT(product_id) AS sku_count,
        SUM(annual_units) AS total_units,
        SUM(annual_revenue) AS total_revenue,
        SUM(annual_cogs) AS total_cogs,
        SUM(gross_margin) AS total_gross_margin,
        (SUM(gross_margin) * 100.0 / SUM(annual_revenue)) AS gross_margin_pct,
        SUM(profit_at_risk) AS total_profit_at_risk,
        (SUM(profit_at_risk) * 100.0 / SUM(gross_margin)) AS sector_mei_pct
    FROM sku_margins
)
SELECT
    sector,
    sku_count,
    total_units,
    ROUND(total_revenue, 2) AS total_revenue,
    ROUND(total_cogs, 2) AS total_cogs,
    ROUND(total_gross_margin, 2) AS total_gross_margin,
    ROUND(gross_margin_pct, 2) AS gross_margin_pct,
    ROUND(total_profit_at_risk, 2) AS total_profit_at_risk,
    ROUND(sector_mei_pct, 2) AS mei_pct
FROM sector_summary
UNION ALL
SELECT
    sector,
    sku_count,
    total_units,
    ROUND(total_revenue, 2) AS total_revenue,
    ROUND(total_cogs, 2) AS total_cogs,
    ROUND(total_gross_margin, 2) AS total_gross_margin,
    ROUND(gross_margin_pct, 2) AS gross_margin_pct,
    ROUND(total_profit_at_risk, 2) AS total_profit_at_risk,
    ROUND(sector_mei_pct, 2) AS mei_pct
FROM portfolio_total;
