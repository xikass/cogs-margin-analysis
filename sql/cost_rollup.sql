-- sql/cost_rollup.sql
-- Cost roll-up CTEs: component cost -> unit cost -> margin -> MEI

WITH component_unit_costs AS (
    SELECT
        b.product_id,
        b.component_id,
        c.name AS component_name,
        c.type AS component_type,
        c.is_imported,
        c.unit_cost AS component_price,
        b.qty_per_unit,
        b.scrap_pct,
        (b.qty_per_unit * (1.0 + b.scrap_pct / 100.0) * c.unit_cost) AS effective_cost_per_unit
    FROM bom_items b
    JOIN components c ON b.component_id = c.component_id
),
component_rollups AS (
    SELECT
        product_id,
        SUM(CASE WHEN component_type = 'API' THEN effective_cost_per_unit ELSE 0.0 END) AS api_cost_per_unit,
        SUM(CASE WHEN component_type = 'EXCIPIENT' THEN effective_cost_per_unit ELSE 0.0 END) AS excipient_cost_per_unit,
        SUM(CASE WHEN component_type = 'PACKAGING' THEN effective_cost_per_unit ELSE 0.0 END) AS packaging_cost_per_unit,
        SUM(CASE WHEN is_imported = 1 THEN effective_cost_per_unit ELSE 0.0 END) AS imported_cost_per_unit,
        SUM(effective_cost_per_unit) AS direct_material_cost,
        MAX(CASE WHEN component_type = 'API' THEN component_price ELSE NULL END) AS current_api_price,
        MAX(CASE WHEN component_type = 'API' THEN (qty_per_unit * (1.0 + scrap_pct / 100.0)) ELSE NULL END) AS api_qty_per_unit
    FROM component_unit_costs
    GROUP BY product_id
),
product_cost_build AS (
    SELECT
        p.product_id,
        p.name AS product_name,
        p.sector,
        p.annual_units,
        p.unit_price,
        p.units_per_batch,
        cr.api_cost_per_unit,
        cr.excipient_cost_per_unit,
        cr.packaging_cost_per_unit,
        cr.imported_cost_per_unit,
        cr.direct_material_cost,
        cr.current_api_price,
        cr.api_qty_per_unit,
        o.labor_per_batch,
        o.overhead_per_batch,
        (o.labor_per_batch * 1.0 / p.units_per_batch) AS labor_cost_per_unit,
        (o.overhead_per_batch * 1.0 / p.units_per_batch) AS overhead_cost_per_unit,
        ((o.labor_per_batch + o.overhead_per_batch) * 1.0 / p.units_per_batch) AS batch_overhead_per_unit,
        (cr.direct_material_cost + ((o.labor_per_batch + o.overhead_per_batch) * 1.0 / p.units_per_batch)) AS unit_cost
    FROM products p
    JOIN component_rollups cr ON p.product_id = cr.product_id
    JOIN overhead o ON p.product_id = o.product_id
),
margin_calculations AS (
    SELECT
        product_id,
        product_name,
        sector,
        annual_units,
        unit_price,
        units_per_batch,
        api_cost_per_unit,
        excipient_cost_per_unit,
        packaging_cost_per_unit,
        imported_cost_per_unit,
        labor_cost_per_unit,
        overhead_cost_per_unit,
        batch_overhead_per_unit,
        unit_cost,
        current_api_price,
        api_qty_per_unit,
        (annual_units * unit_price) AS annual_revenue,
        (annual_units * unit_cost) AS annual_cogs,
        ((annual_units * unit_price) - (annual_units * unit_cost)) AS gross_margin,
        CASE
            WHEN (annual_units * unit_price) > 0 THEN (((annual_units * unit_price) - (annual_units * unit_cost)) * 100.0 / (annual_units * unit_price))
            ELSE 0.0
        END AS gross_margin_pct,
        CASE
            WHEN unit_cost > 0 THEN (api_cost_per_unit / unit_cost)
            ELSE 0.0
        END AS api_share
    FROM product_cost_build
)
SELECT
    product_id,
    product_name,
    sector,
    annual_units,
    unit_price,
    units_per_batch,
    ROUND(api_cost_per_unit, 4) AS api_cost_per_unit,
    ROUND(excipient_cost_per_unit, 4) AS excipient_cost_per_unit,
    ROUND(packaging_cost_per_unit, 4) AS packaging_cost_per_unit,
    ROUND(imported_cost_per_unit, 4) AS imported_cost_per_unit,
    ROUND(labor_cost_per_unit, 4) AS labor_cost_per_unit,
    ROUND(overhead_cost_per_unit, 4) AS overhead_cost_per_unit,
    ROUND(unit_cost, 4) AS unit_cost,
    ROUND(current_api_price, 2) AS current_api_price,
    ROUND(annual_revenue, 2) AS annual_revenue,
    ROUND(annual_cogs, 2) AS annual_cogs,
    ROUND(gross_margin, 2) AS gross_margin,
    ROUND(gross_margin_pct, 2) AS gross_margin_pct,
    ROUND(api_share, 4) AS api_share,
    ROUND((annual_cogs * api_share * 0.10), 2) AS profit_at_risk,
    CASE
        WHEN gross_margin <= 0 THEN 1
        ELSE 0
    END AS is_negative_margin,
    CASE
        WHEN gross_margin > 0 THEN ROUND(((annual_cogs * api_share * 0.10) / gross_margin) * 100.0, 2)
        ELSE NULL
    END AS mei_pct,
    CASE
        WHEN gross_margin > 0 AND (annual_cogs * api_share) > 0 THEN
            ROUND(current_api_price * (1.0 + (gross_margin / (annual_cogs * api_share))), 2)
        ELSE NULL
    END AS break_even_api_price
FROM margin_calculations
ORDER BY mei_pct DESC;
