"""
generate_data.py - Synthetic pharmaceutical COGS dataset generator.
Generates products, components, BOM items, and overhead cost data for 4 sectors:
COSMETICS, HUMAN_PHARMA, VETERINARY, and FOOD_SUPPLEMENT.
Injects ~2% dirty data records for data quality audit verification.
Saves SQLite database to data/cogs.db and CSVs to data/.
"""

import os
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

def generate_synthetic_cogs_data(seed: int = 42, output_dir: str = None):
    np.random.seed(seed)
    if output_dir is None:
        output_dir = str(REPO_ROOT / "data")
    os.makedirs(output_dir, exist_ok=True)
    db_path = os.path.join(output_dir, "cogs.db")

    # 1. PRODUCTS (40 SKUs across 4 sectors)
    sectors = ["HUMAN_PHARMA", "COSMETICS", "VETERINARY", "FOOD_SUPPLEMENT"]

    product_names = {
        "HUMAN_PHARMA": [
            "Amoxicillin 500mg Caps", "Paracetamol 500mg Tabs", "Metformin 850mg Tabs",
            "Ciprofloxacin 500mg Tabs", "Omeprazole 20mg Caps", "Atorvastatin 20mg Tabs",
            "Azithromycin 500mg Tabs", "Losartan 50mg Tabs", "Ibuprofen 400mg Tabs",
            "Cetirizine 10mg Tabs"
        ],
        "COSMETICS": [
            "Hyaluronic Acid Serum 30ml", "Vitamin C Brightening Cream 50ml",
            "Niacinamide Clarifying Gel 50ml", "Retinol Night Cream 50ml",
            "SPF 50 Mineral Sunscreen 100ml", "Ceramide Barrier Lotion 200ml",
            "Salicylic Acid Cleanser 150ml", "Peptide Firming Eye Cream 15ml",
            "Argan Hair Treatment Oil 100ml", "Rosewater Hydrating Toner 200ml"
        ],
        "VETERINARY": [
            "Ivermectin 1% Injectable 50ml", "Enrofloxacin 10% Oral Sol 100ml",
            "Oxytetracycline 20% LA 100ml", "Fenbendazole 10% Susp 250ml",
            "Doxycycline 100mg Vet Tabs", "Meloxicam 1.5mg/ml Oral Susp 30ml",
            "Tilmicosin 300mg Injection 100ml", "Albendazole 2.5% Drench 1000ml",
            "Amox-Clav 250mg Vet Tabs", "Fipronil Spot-On Pipettes 3pk"
        ],
        "FOOD_SUPPLEMENT": [
            "Vitamin D3 5000 IU Softgels", "Omega-3 Triple Fish Oil 1000mg",
            "Magnesium Glycinate 400mg", "Zinc Picolinate 50mg Tabs",
            "Iron Bisglycinate Complex 60s", "CoQ10 200mg Softgels",
            "Probiotic 50 Billion CFU", "Active B-Complex High Potency",
            "Calcium Citrate + D3 120s", "Ashwagandha KSM-66 600mg"
        ]
    }

    products = []
    prod_idx = 1
    for sector in sectors:
        names = product_names[sector]
        for name in names:
            p_id = f"PRD-{prod_idx:03d}"
            # Realistic commercial volumes and prices per sector
            if sector == "HUMAN_PHARMA":
                annual_units = int(np.random.choice([80000, 120000, 150000, 200000, 300000]))
                unit_price = round(float(np.random.uniform(8.50, 28.00)), 2)
                units_per_batch = int(np.random.choice([10000, 20000, 25000]))
            elif sector == "COSMETICS":
                annual_units = int(np.random.choice([40000, 60000, 90000, 120000]))
                unit_price = round(float(np.random.uniform(14.00, 48.00)), 2)
                units_per_batch = int(np.random.choice([5000, 10000, 15000]))
            elif sector == "VETERINARY":
                annual_units = int(np.random.choice([30000, 50000, 80000, 110000]))
                unit_price = round(float(np.random.uniform(12.00, 42.00)), 2)
                units_per_batch = int(np.random.choice([5000, 10000, 20000]))
            else:  # FOOD_SUPPLEMENT
                annual_units = int(np.random.choice([60000, 90000, 140000, 220000]))
                unit_price = round(float(np.random.uniform(10.00, 32.00)), 2)
                units_per_batch = int(np.random.choice([10000, 15000, 25000]))

            products.append({
                "product_id": p_id,
                "name": name,
                "sector": sector,
                "annual_units": annual_units,
                "unit_price": unit_price,
                "units_per_batch": units_per_batch
            })
            prod_idx += 1

    df_products = pd.DataFrame(products)

    # 2. COMPONENTS (120 components)
    # 40 APIs (CMP-001 to CMP-040), one primary per product
    # 50 Excipients (CMP-041 to CMP-090)
    # 30 Packaging items (CMP-091 to CMP-120)
    suppliers = [
        "Apex BioChem Ltd", "SolvChem Global", "Aegis Polymers Inc",
        "PurePharma Specialties", "Nordic Ingredients A/S", "BioPack Container Corp",
        "Zhejiang FineChem", "Alpine Pharma Supplies", "Vantage Excipients",
        "Omega Lipid Works"
    ]

    components = []
    # 40 APIs
    api_names = [
        "Amoxicillin Trihydrate USP", "Paracetamol Fine Powder", "Metformin HCl BP",
        "Ciprofloxacin HCl BP", "Omeprazole Pellets 8.5%", "Atorvastatin Calcium USP",
        "Azithromycin Dihydrate", "Losartan Potassium BP", "Ibuprofen Granular 90%",
        "Cetirizine Di-HCl USP",
        "Sodium Hyaluronate 1.5MDa", "Sodium Ascorbyl Phosphate", "Niacinamide Pure 99%",
        "Pure Retinol 50S Complex", "Zinc Oxide Micro 60%", "Ceramide Complex NP/AP/EOP",
        "Salicylic Acid Sublimed", "Matrixyl 3000 Peptide Sol", "Cold-Pressed Argan Oil",
        "Organic Rose Damascena Distillate",
        "Ivermectin Micronized EP", "Enrofloxacin Base USP", "Oxytetracycline Dihydrate",
        "Fenbendazole Vet Grade", "Doxycycline Hyclate BP", "Meloxicam Micronized",
        "Tilmicosin Technical Base", "Albendazole Micronized BP", "Amoxicillin/Pot Clavulanate",
        "Fipronil Technical 98%",
        "Vitamin D3 Crystal 40M IU/g", "Fish Oil EPA/DHA 50/20 EE", "Magnesium Bisglycinate Pure",
        "Zinc Picolinate Chelate 20%", "Ferrous Bisglycinate 20% Fe", "Coenzyme Q10 Pure 99%",
        "Probiotic Blend 100B CFU/g", "B-Complex Active Coenzymes", "Calcium Citrate Malate 24%",
        "Ashwagandha Root Extract 5%"
    ]
    for i in range(1, 41):
        c_id = f"CMP-{i:03d}"
        supplier = suppliers[i % len(suppliers)]
        is_imported = 1 if (i % 3 != 0) else 0
        # Realistic API costs ($20 to $320 per kg)
        unit_cost = round(float(np.random.uniform(28.0, 260.0)), 2)
        components.append({
            "component_id": c_id,
            "name": api_names[i - 1],
            "type": "API",
            "supplier": supplier,
            "unit_cost": unit_cost,
            "is_imported": is_imported
        })

    # 50 Excipients (CMP-041 to CMP-090)
    excipient_names = [
        "Microcrystalline Cellulose PH102", "Lactose Monohydrate 200M", "Magnesium Stearate Pharma",
        "Colloidal Silicon Dioxide", "Croscarmellose Sodium", "Povidone K30 USP",
        "Hydroxypropyl Methylcellulose", "Corn Starch Pharmaceutical", "Sodium Starch Glycolate",
        "Purified Water USP", "Propylene Glycol Pharma", "Vegetable Glycerin 99.7%",
        "Citric Acid Anhydrous", "Sodium Citrate Dihydrate", "Xanthan Gum 200 Mesh",
        "Carbomer 940 Polymer", "Triethanolamine 99%", "Cetearyl Alcohol 50/50",
        "Ceteareth-20 Emulsifier", "Dimethicone 350 cSt", "Caprylic/Capric Triglyceride",
        "Shea Butter Refined", "Polysorbate 80 Tween", "Sorbitol 70% Solution",
        "Methylparaben BP/USP", "Propylparaben BP/USP", "Phenoxyethanol Pure",
        "Ethylhexylglycerin", "Disodium EDTA USP", "Tocopherol Acetate Vitamin E",
        "Sodium Hydroxide 1N Pellets", "Hydrochloric Acid 37% Pharma", "Ethanol 96% Denatured",
        "Isopropyl Alcohol 99.9%", "Polyethylene Glycol 400", "Polyethylene Glycol 4000",
        "Sodium Chloride USP Granular", "Potassium Sorbate Food Grade", "Sodium Benzoate BP",
        "Lecithin Soya De-oiled", "Medium Chain Triglycerides", "Flavor Peppermint Natural",
        "Flavor Sweet Orange USP", "Sucralose Micronized Powder", "Titanium Dioxide White",
        "Iron Oxide Red Pigment", "Iron Oxide Yellow Pigment", "Maltodextrin 18DE",
        "Silicon Dioxide Anti-Caking", "Dicalcium Phosphate Anhydrous"
    ]
    for i in range(41, 91):
        c_id = f"CMP-{i:03d}"
        supplier = suppliers[i % len(suppliers)]
        is_imported = 1 if (i % 2 == 0) else 0
        unit_cost = round(float(np.random.uniform(1.80, 16.50)), 2)
        components.append({
            "component_id": c_id,
            "name": excipient_names[i - 41],
            "type": "EXCIPIENT",
            "supplier": supplier,
            "unit_cost": unit_cost,
            "is_imported": is_imported
        })

    # 30 Packaging components (CMP-091 to CMP-120)
    packaging_names = [
        "Blister PVC/PVDC Film 250mic", "Hard Aluminum Blister Foil 20mic", "Unit Folding Box 350gsm",
        "HDPE Wide Mouth Bottle 100ml", "Child Resistant Cap 38mm", "Induction Heat Seal Liner 38mm",
        "Amber Glass Dropper Bottle 30ml", "Glass Pipette Dropper Assembly", "Plastic Pump Dispenser 24/410",
        "Laminate Tube Aluminum-Plastic 50ml", "Flip-Top Dispensing Cap 24mm", "Corrugated Shipper Outer Box",
        "Self-Adhesive BOPP Label 4-Color", "Tamper Evident Shrink Sleeve", "Desiccant Silica Gel Canister 1g",
        "Amber Glass Serum Bottle 50ml", "HDPE Pill Jar 250ml", "CRC Screw Cap 45mm",
        "PET Bottle Clear 200ml", "Mist Spray Pump Actuator", "Aluminum Airless Pump Dispenser 50ml",
        "Secondary Display Outer Box", "Polyethylene Drench Bottle 1000ml", "Drench Nozzle Cap Adapter",
        "Multi-Dose Vial Type I Glass 50ml", "Bromobutyl Rubber Stopper 20mm", "Aluminum Tear-Off Flip Cap 20mm",
        "Fipronil Pipette Blister Shell 3pk", "Blister Foil Push-Through 250x0.02", "Instruction Patient Leaflet 45gsm"
    ]
    for i in range(91, 121):
        c_id = f"CMP-{i:03d}"
        supplier = suppliers[i % len(suppliers)]
        is_imported = 1 if (i % 3 == 1) else 0
        unit_cost = round(float(np.random.uniform(0.12, 1.95)), 2)
        components.append({
            "component_id": c_id,
            "name": packaging_names[i - 91],
            "type": "PACKAGING",
            "supplier": supplier,
            "unit_cost": unit_cost,
            "is_imported": is_imported
        })

    df_components = pd.DataFrame(components)

    # 3. BOM ITEMS (3-6 components per product)
    # Exactly: 1 API + 2-3 Excipients + 1-2 Packaging items
    bom_items = []
    for p_idx in range(1, 41):
        p_id = f"PRD-{p_idx:03d}"
        # Primary API: CMP-001 to CMP-040 mapped 1:1
        api_id = f"CMP-{p_idx:03d}"
        # Quantity per unit: 0.005 to 0.080 kg/unit (or unit scale)
        # Choose qty so api_cost is 20% to 55% of product unit cost
        p_price = df_products.loc[df_products["product_id"] == p_id, "unit_price"].values[0]
        api_unit_cost = df_components.loc[df_components["component_id"] == api_id, "unit_cost"].values[0]
        target_api_spend = p_price * np.random.uniform(0.12, 0.32)
        api_qty = max(0.002, round(target_api_spend / api_unit_cost, 4))
        scrap_api = round(float(np.random.uniform(0.5, 2.5)), 2)

        bom_items.append({
            "product_id": p_id,
            "component_id": api_id,
            "qty_per_unit": api_qty,
            "scrap_pct": scrap_api
        })

        # 2 Excipients
        num_excipients = int(np.random.choice([2, 3]))
        exc_ids = np.random.choice(range(41, 91), size=num_excipients, replace=False)
        for exc_id_num in exc_ids:
            exc_id = f"CMP-{exc_id_num:03d}"
            exc_qty = round(float(np.random.uniform(0.015, 0.120)), 4)
            scrap_exc = round(float(np.random.uniform(1.0, 3.0)), 2)
            bom_items.append({
                "product_id": p_id,
                "component_id": exc_id,
                "qty_per_unit": exc_qty,
                "scrap_pct": scrap_exc
            })

        # 2 Packaging items (e.g. 1 bottle/blister + 1 cap/box)
        num_pkg = int(np.random.choice([1, 2]))
        pkg_ids = np.random.choice(range(91, 121), size=num_pkg, replace=False)
        for pkg_id_num in pkg_ids:
            pkg_id = f"CMP-{pkg_id_num:03d}"
            pkg_qty = 1.0
            scrap_pkg = round(float(np.random.uniform(0.5, 2.0)), 2)
            bom_items.append({
                "product_id": p_id,
                "component_id": pkg_id,
                "qty_per_unit": pkg_qty,
                "scrap_pct": scrap_pkg
            })

    df_bom = pd.DataFrame(bom_items)

    # 4. OVERHEAD (labor and indirect manufacturing overhead per batch)
    overhead = []
    for p_idx in range(1, 41):
        p_id = f"PRD-{p_idx:03d}"
        sector = df_products.loc[df_products["product_id"] == p_id, "sector"].values[0]
        if sector == "HUMAN_PHARMA":
            labor = round(float(np.random.uniform(1800.0, 3400.0)), 2)
            ovh = round(float(np.random.uniform(2200.0, 4200.0)), 2)
        elif sector == "VETERINARY":
            labor = round(float(np.random.uniform(1400.0, 2600.0)), 2)
            ovh = round(float(np.random.uniform(1800.0, 3200.0)), 2)
        elif sector == "COSMETICS":
            labor = round(float(np.random.uniform(900.0, 1800.0)), 2)
            ovh = round(float(np.random.uniform(1200.0, 2400.0)), 2)
        else:  # FOOD_SUPPLEMENT
            labor = round(float(np.random.uniform(1100.0, 2000.0)), 2)
            ovh = round(float(np.random.uniform(1400.0, 2600.0)), 2)

        overhead.append({
            "product_id": p_id,
            "sector": sector,
            "labor_per_batch": labor,
            "overhead_per_batch": ovh
        })
    df_overhead = pd.DataFrame(overhead)

    # 5. INJECT ~2% DIRTY ROWS AS REQUIRED
    # - 2 duplicate BOM rows
    dup_rows = df_bom.sample(2, random_state=101)
    df_bom_dirty = pd.concat([df_bom, dup_rows], ignore_index=True)

    # - 3 orphan BOM rows (non-existent product or non-existent component)
    orphan_boms = pd.DataFrame([
        {"product_id": "PRD-999", "component_id": "CMP-010", "qty_per_unit": 0.05, "scrap_pct": 1.0},
        {"product_id": "PRD-015", "component_id": "CMP-999", "qty_per_unit": 0.02, "scrap_pct": 1.5},
        {"product_id": "PRD-888", "component_id": "CMP-888", "qty_per_unit": 0.10, "scrap_pct": 2.0}
    ])
    df_bom_dirty = pd.concat([df_bom_dirty, orphan_boms], ignore_index=True)

    # - 2 null unit_cost in components
    df_components_dirty = df_components.copy()
    null_indices = [45, 78]  # CMP-046, CMP-079 (excipients)
    for idx in null_indices:
        df_components_dirty.loc[idx, "unit_cost"] = np.nan

    # - 2 negative costs in components
    neg_indices = [52, 95]  # CMP-053, CMP-096
    for idx in neg_indices:
        df_components_dirty.loc[idx, "unit_cost"] = -abs(df_components_dirty.loc[idx, "unit_cost"])

    # - 2 products with zero units_per_batch
    df_products_dirty = df_products.copy()
    df_products_dirty.loc[7, "units_per_batch"] = 0   # PRD-008
    df_products_dirty.loc[23, "units_per_batch"] = 0  # PRD-024

    # - 2 products with unit_price <= 0
    df_products_dirty.loc[12, "unit_price"] = 0.00   # PRD-013
    df_products_dirty.loc[31, "unit_price"] = -14.50 # PRD-032

    # Save CSVs (dirty data representing ERP raw extract)
    df_products_dirty.to_csv(os.path.join(output_dir, "products.csv"), index=False)
    df_components_dirty.to_csv(os.path.join(output_dir, "components.csv"), index=False)
    df_bom_dirty.to_csv(os.path.join(output_dir, "bom_items.csv"), index=False)
    df_overhead.to_csv(os.path.join(output_dir, "overhead.csv"), index=False)

    # Save to SQLite
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    df_products_dirty.to_sql("products", conn, if_exists="replace", index=False)
    df_components_dirty.to_sql("components", conn, if_exists="replace", index=False)
    df_bom_dirty.to_sql("bom_items", conn, if_exists="replace", index=False)
    df_overhead.to_sql("overhead", conn, if_exists="replace", index=False)
    conn.close()

    print(f"Data generation complete: 40 products, 120 components, {len(df_bom_dirty)} BOM rows, {len(df_overhead)} overhead rows.")
    print(f"Saved database to {db_path} and CSVs to {output_dir}/")

if __name__ == "__main__":
    generate_synthetic_cogs_data()
