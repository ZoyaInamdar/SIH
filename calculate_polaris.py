import os
import sys
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from master.route_manager import get_active_corridor

POLARIS_RIV_TABLE = {
    "Ice-free water":     {"PC1": 3, "PC2": 3, "PC3": 3, "PC4": 3, "PC5": 3, "PC6": 3, "PC7": 3},
    "New ice":            {"PC1": 3, "PC2": 3, "PC3": 3, "PC4": 3, "PC5": 3, "PC6": 2, "PC7": 2},
    "Grey ice":           {"PC1": 3, "PC2": 3, "PC3": 3, "PC4": 3, "PC5": 3, "PC6": 2, "PC7": 2},
    "Grey-white ice":     {"PC1": 3, "PC2": 3, "PC3": 3, "PC4": 3, "PC5": 3, "PC6": 2, "PC7": 2},
    "Thin FYI 1st stage": {"PC1": 2, "PC2": 2, "PC3": 2, "PC4": 2, "PC5": 2, "PC6": 2, "PC7": 1},
    "Thin FYI 2nd stage": {"PC1": 2, "PC2": 2, "PC3": 2, "PC4": 2, "PC5": 2, "PC6": 1, "PC7": 1},
    "Medium FYI <1 m":    {"PC1": 2, "PC2": 2, "PC3": 2, "PC4": 2, "PC5": 1, "PC6": 1, "PC7": 0},
    "Medium FYI":         {"PC1": 2, "PC2": 2, "PC3": 2, "PC4": 2, "PC5": 1, "PC6": 0, "PC7": -1},
    "Thick FYI":          {"PC1": 2, "PC2": 2, "PC3": 1, "PC4": 1, "PC5": 0, "PC6": -1, "PC7": -2},
    "Second-year ice":    {"PC1": 2, "PC2": 1, "PC3": 1, "PC4": 0, "PC5": -1, "PC6": -2, "PC7": -3},
    "Light MYI <2.5 m":   {"PC1": 1, "PC2": 1, "PC3": 0, "PC4": -1, "PC5": -2, "PC6": -3, "PC7": -3},
    "Heavy MYI":          {"PC1": 1, "PC2": 0, "PC3": -1, "PC4": -2, "PC5": -2, "PC6": -3, "PC7": -3},
}

SUPPORTED_VESSEL_CLASSES = ["PC1", "PC2", "PC3", "PC4", "PC5", "PC6", "PC7"]

def calculate_rio(partial_concentrations, vessel_class):
    return np.nan

def classify_cell(sic, ice_type, sit, vessel_class):
    sic_frac = sic if sic <= 1.0 else sic / 100.0
    
    sit_valid = bool(pd.notna(sit) and np.isfinite(sit) and sit > 0)
    
    ice_type_str = str(ice_type).lower().strip()
    ice_type_missing = bool(pd.isna(ice_type) or ice_type_str == "" or ice_type_str in ["nan", "missing", "unknown"])
    
    valid_categories = ["open_water", "first_year_ice", "multi_year_ice", "ambiguous", "missing", "unknown"]
    
    if ice_type_missing:
        ice_type_str = "missing"
    elif ice_type_str not in valid_categories:
        ice_type_str = "unknown"
        
    ice_type_ambiguous = (ice_type_str == "ambiguous")

    cat = np.nan
    rio = np.nan
    riv = np.nan
    dliri = np.nan
    effective_thickness = np.nan
    thickness_factor = np.nan
    operational_risk = "UNKNOWN"
    risk_source = "UNKNOWN"
    confidence = "unknown"
    status = "nominal"
    fallback_used = False
    fallback_reason = ""
    rio_method = "NOT_AVAILABLE"
    rio_available = False
    
    def set_polaris(c, conf, st="nominal"):
        nonlocal cat, rio, riv, operational_risk, risk_source, confidence, status, rio_method, rio_available
        cat = c
        riv = POLARIS_RIV_TABLE[cat][vessel_class]
        
        rio = calculate_rio({}, vessel_class) 
        
        if pd.notna(rio):
            rio_method = "POLARIS_FULL"
            rio_available = True
            if rio >= 0.0:
                operational_risk = "NORMAL"
            elif rio >= -10.0:
                operational_risk = "ELEVATED"
            else:
                operational_risk = "SPECIAL_CONSIDERATION"
        else:
            rio_method = "NOT_AVAILABLE"
            rio_available = False
            operational_risk = "UNKNOWN"
            
        risk_source = "POLARIS"
        confidence = conf
        status = st
            
    def get_dliri_cat(val):
        if val <= 20: return "LOW"
        if val <= 40: return "MODERATE"
        if val <= 60: return "ELEVATED"
        if val <= 80: return "HIGH"
        return "VERY_HIGH"

    def set_dliri(d, rs, conf, st="nominal"):
        nonlocal dliri, operational_risk, risk_source, confidence, status
        dliri = round(d, 4)
        risk_source = rs
        confidence = conf
        status = st
        operational_risk = get_dliri_cat(dliri)

    if sit_valid:
        effective_thickness = round(sic_frac * sit, 4)

    if sic_frac < 0.10:
        set_polaris("Ice-free water", "high")
    else:
        if ice_type_str == "open_water":
            set_dliri(100.0 * sic_frac, "SIC_ONLY", "very_low", "inconsistent_sic_ice_type")
        elif ice_type_str == "first_year_ice":
            if not sit_valid:
                st = "invalid_SIT" if (pd.notna(sit) and sit == 0) else "missing_SIT"
                fallback_used = True
                fallback_reason = "conservative_project_defined_fallback"
                set_polaris("Thick FYI", "fallback", st)
            else:
                if sit < 0.10: c = "New ice"
                elif sit < 0.15: c = "Grey ice"
                elif sit < 0.30: c = "Grey-white ice"
                elif sit < 0.50: c = "Thin FYI 1st stage"
                elif sit < 0.70: c = "Thin FYI 2nd stage"
                elif sit < 1.00: c = "Medium FYI <1 m"
                elif sit <= 1.20: c = "Medium FYI"
                else: c = "Thick FYI"
                set_polaris(c, "high")
        elif ice_type_str == "multi_year_ice":
            if not sit_valid:
                st = "invalid_SIT" if (pd.notna(sit) and sit == 0) else "missing_SIT"
                fallback_used = True
                fallback_reason = "conservative_project_defined_fallback"
                set_polaris("Heavy MYI", "fallback", st)
            else:
                c = "Light MYI <2.5 m" if sit < 2.50 else "Heavy MYI"
                set_polaris(c, "high")
        else:
            if not sit_valid:
                st = "invalid_SIT" if (pd.notna(sit) and sit == 0) else "missing_SIT"
                set_dliri(100.0 * sic_frac, "SIC_ONLY", "very_low", st)
            else:
                thickness_factor = min(sit / 2.5, 1.0)
                d = 100.0 * sic_frac * (0.30 + 0.70 * thickness_factor)
                d = max(0, min(d, 100.0))
                set_dliri(d, "DLIRI", "low")

    dliri_cat = get_dliri_cat(dliri) if pd.notna(dliri) else np.nan

    return {
        'SIC': sic_frac,
        'Ice_Type': ice_type,
        'Ice_Type_Norm': ice_type_str,
        'SIT': sit,
        'vessel_class': vessel_class,
        'polaris_ice_category': cat,
        'RIV': riv,
        'RIO': rio,
        'rio_method': rio_method,
        'rio_available': rio_available,
        'DLIRI': dliri,
        'DLIRI_category': dliri_cat,
        'effective_thickness': effective_thickness,
        'thickness_factor': thickness_factor,
        'operational_risk': operational_risk,
        'risk_source': risk_source,
        'confidence': confidence,
        'status': status,
        'fallback_used': fallback_used,
        'fallback_reason': fallback_reason,
        'sit_valid': sit_valid,
        'ice_type_missing': ice_type_missing,
        'ice_type_ambiguous': ice_type_ambiguous
    }

def validate_pipeline(df_out):
    print("\n" + "=" * 65)
    print("RUNNING FINAL VALIDATION TESTS")
    print("=" * 65)
    passed_all = True
    
    def assert_test(name, condition_mask, rule_mask):
        nonlocal passed_all
        matching_cells = condition_mask.sum()
        print(f"Test {name}")
        print(f"  Matching cells: {matching_cells}")
        if matching_cells == 0:
            print("  Status: NOT EXERCISED\n")
        else:
            if rule_mask[condition_mask].all():
                print("  Status: PASSED\n")
            else:
                print("  Status: FAILED\n")
                passed_all = False

    ice = df_out['Ice_Type_Norm']
    sit_valid = df_out['sit_valid']
    sit = df_out['SIT']
    sic = df_out['SIC']
    sit_zero = (sit == 0)

    no_iceberg = ~df_out.get('iceberg_presence', pd.Series([False]*len(df_out)))

    assert_test("1 — Ambiguous + valid SIT -> DLIRI",
                (ice == "ambiguous") & sit_valid & (sic >= 0.10) & no_iceberg,
                df_out['risk_source'] == "DLIRI")

    assert_test("2 — Missing Ice Type + valid SIT -> DLIRI",
                (ice == "missing") & sit_valid & (sic >= 0.10) & no_iceberg,
                df_out['risk_source'] == "DLIRI")

    assert_test("3 — Ambiguous + SIT=0 -> SIC_ONLY",
                (ice == "ambiguous") & sit_zero & (sic >= 0.10) & no_iceberg,
                df_out['risk_source'] == "SIC_ONLY")

    assert_test("4 — Missing Ice Type + SIT=0 -> SIC_ONLY",
                (ice == "missing") & sit_zero & (sic >= 0.10) & no_iceberg,
                df_out['risk_source'] == "SIC_ONLY")

    assert_test("5 — FYI + valid SIT -> POLARIS",
                (ice == "first_year_ice") & sit_valid & (sic >= 0.10) & no_iceberg,
                df_out['risk_source'] == "POLARIS")

    assert_test("6 — MYI + valid SIT -> POLARIS",
                (ice == "multi_year_ice") & sit_valid & (sic >= 0.10) & no_iceberg,
                df_out['risk_source'] == "POLARIS")

    assert_test("7 — FYI + missing SIT -> Thick FYI POLARIS fallback",
                (ice == "first_year_ice") & (~sit_valid) & (~sit_zero) & (sic >= 0.10),
                df_out['polaris_ice_category'] == "Thick FYI")

    assert_test("8 — MYI + missing SIT -> Heavy MYI POLARIS fallback",
                (ice == "multi_year_ice") & (~sit_valid) & (~sit_zero) & (sic >= 0.10),
                df_out['polaris_ice_category'] == "Heavy MYI")

    assert_test("9 — SIC < 0.10 -> Ice-free POLARIS",
                (sic < 0.10) & no_iceberg,
                (df_out['polaris_ice_category'] == "Ice-free water") & (df_out['risk_source'] == "POLARIS"))

    assert_test("10 — SIC >=0.10 + open_water -> SIC_ONLY + inconsistency flag",
                (sic >= 0.10) & (ice == "open_water"),
                (df_out['risk_source'] == "SIC_ONLY") & (df_out['status'] == "inconsistent_sic_ice_type"))

    nn_mask = (df_out['ice_type_match_method'] == 'nearest')
    assert_test("B — match distance <= 15 km", nn_mask, df_out['ice_type_match_distance_km'] <= 15.0)

    miss_mask = (df_out['ice_type_match_method'] == 'missing')
    assert_test("D — missing match has NaN distance", miss_mask, df_out['ice_type_match_distance_km'].isna())

    dliri_mask = (df_out['risk_source'] == "DLIRI")
    def dliri_check(s):
        tf = np.minimum(s['SIT'] / 2.5, 1.0)
        expected = 100.0 * s['SIC'] * (0.30 + 0.70 * tf)
        expected = np.clip(expected, 0, 100.0)
        return np.isclose(s['DLIRI'], expected, atol=1e-3)
    
    assert_test("F — DLIRI equation exactly matches",
                dliri_mask,
                df_out.apply(dliri_check, axis=1))

    assert_test("H — No SICxRIV is used as RIO (RIO is NaN or rio_method=POLARIS_FULL)",
                df_out['RIO'].notna(),
                df_out['rio_method'] == "POLARIS_FULL")

    assert_test("I — Ambiguous + valid SIT -> DLIRI + RIO NaN + RIV NaN",
                (ice == "ambiguous") & sit_valid & (sic >= 0.10),
                (df_out['risk_source'] == "DLIRI") & df_out['RIO'].isna() & df_out['RIV'].isna())

    assert_test("J — Missing Ice Type + valid SIT -> DLIRI + RIO NaN + RIV NaN",
                (ice == "missing") & sit_valid & (sic >= 0.10),
                (df_out['risk_source'] == "DLIRI") & df_out['RIO'].isna() & df_out['RIV'].isna())

    assert_test("K — SIC_ONLY -> RIO NaN + RIV NaN",
                (df_out['risk_source'] == "SIC_ONLY"),
                df_out['RIO'].isna() & df_out['RIV'].isna())

    assert_test("L — RIV exists while RIO is NaN (Valid POLARIS cat but no conc vector)",
                df_out['RIV'].notna(),
                df_out['RIO'].isna())

    if 'iceberg_presence' in df_out:
        assert_test("M — Iceberg presence forces Extreme risk",
                    df_out['iceberg_presence'] == True,
                    (df_out['operational_risk'] == "EXTREME") & (df_out['risk_source'] == "ICEBERG_COLLISION_ZONE"))

    if not passed_all:
        print("[WARNING] Validation failed on some criteria.")
    else:
        print("[SUCCESS] All evaluated validation criteria passed.")
    return passed_all

def generate_maps(df_out, gdf_route, corridor_polygon, vessel_class, run_dir):
    print("\nGenerating 8-panel diagnostic visualization...")
    fig, axes = plt.subplots(2, 4, figsize=(24, 12))
    axes = axes.flatten()

    def plot_base(ax, title):
        gdf_route.plot(ax=ax, color='black', linewidth=2, zorder=5)
        gpd.GeoSeries([corridor_polygon]).plot(ax=ax, facecolor='none', edgecolor='blue', linestyle='--', zorder=4)
        ax.set_title(title, fontsize=12)
        ax.set_xticks([])
        ax.set_yticks([])

    ax = axes[0]
    plot_base(ax, "1. POLARIS RIO — FULL CONCENTRATION ONLY")
    df_polaris = df_out.dropna(subset=['RIO'])
    if not df_polaris.empty:
        sc = ax.scatter(df_polaris['longitude'], df_polaris['latitude'], c=df_polaris['RIO'], cmap='coolwarm_r', s=8, vmin=-3, vmax=3, zorder=3)
        plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    else:
        ax.text(0.5, 0.5, "No full POLARIS\nconcentration data", 
                horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=12, color='red')

    ax = axes[1]
    plot_base(ax, "2. DLIRI Score")
    df_dliri = df_out.dropna(subset=['DLIRI'])
    if not df_dliri.empty:
        sc = ax.scatter(df_dliri['longitude'], df_dliri['latitude'], c=df_dliri['DLIRI'], cmap='RdYlGn_r', s=8, vmin=0, vmax=100, zorder=3)
        plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[2]
    plot_base(ax, "3. Risk Source")
    source_map = {"POLARIS": 2, "DLIRI": 1, "SIC_ONLY": 0}
    c_source = [source_map.get(str(x), -1) for x in df_out['risk_source']]
    cmap_src = ListedColormap(['#d62728', '#ff7f0e', '#2ca02c']) 
    sc = ax.scatter(df_out['longitude'], df_out['latitude'], c=c_source, cmap=cmap_src, s=8, vmin=-0.5, vmax=2.5, zorder=3)
    cbar = plt.colorbar(sc, ax=ax, ticks=[0, 1, 2], fraction=0.046, pad=0.04)
    cbar.ax.set_yticklabels(['SIC_ONLY', 'DLIRI', 'POLARIS'])

    ax = axes[3]
    plot_base(ax, "4. Confidence")
    conf_map = {"high": 3, "fallback": 2, "low": 1, "very_low": 0}
    c_conf = [conf_map.get(str(x), -1) for x in df_out['confidence']]
    cmap_conf = ListedColormap(['#d62728', '#ff7f0e', '#bcbd22', '#2ca02c'])
    sc = ax.scatter(df_out['longitude'], df_out['latitude'], c=c_conf, cmap=cmap_conf, s=8, vmin=-0.5, vmax=3.5, zorder=3)
    cbar = plt.colorbar(sc, ax=ax, ticks=[0, 1, 2, 3], fraction=0.046, pad=0.04)
    cbar.ax.set_yticklabels(['very_low', 'low', 'fallback', 'high'])

    ax = axes[4]
    plot_base(ax, "5. Ice-Type Match Dist (km)")
    df_dist = df_out.dropna(subset=['ice_type_match_distance_km'])
    if not df_dist.empty:
        sc = ax.scatter(df_dist['longitude'], df_dist['latitude'], c=df_dist['ice_type_match_distance_km'], cmap='viridis', s=8, vmin=0, vmax=15, zorder=3)
        plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
        
    ax = axes[5]
    plot_base(ax, "6. SIT (Sea Ice Thickness)")
    sc = ax.scatter(df_out['longitude'], df_out['latitude'], c=df_out['SIT'], cmap='plasma', s=8, vmin=0, vmax=3, zorder=3)
    plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[6]
    plot_base(ax, "7. SIC (Sea Ice Concentration)")
    sc = ax.scatter(df_out['longitude'], df_out['latitude'], c=df_out['SIC'], cmap='Blues_r', s=8, vmin=0, vmax=1, zorder=3)
    plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[7]
    ax.axis('off')

    plt.tight_layout()
    plt.savefig(os.path.join(run_dir, "polaris_diagnostic_maps.png"), dpi=200)
    plt.close()
    print("✓ Saved diagnostic visualization to polaris_diagnostic_maps.png")


def run(vessel_class="PC4", run_dir="."):
    if vessel_class not in SUPPORTED_VESSEL_CLASSES:
        raise ValueError(f"Unsupported vessel class '{vessel_class}'. Must be one of {SUPPORTED_VESSEL_CLASSES}")

    print("=" * 65)
    print(f"POLARIS Risk Index Assessment — Vessel Class: {vessel_class}")
    print("=" * 65)

    sic_file = os.path.join(run_dir, "sic_today.csv")
    sit_file = os.path.join(run_dir, "sit_grid.csv")
    ice_file = os.path.join(run_dir, "ice_type_latest.csv")
    iceberg_file = os.path.join(run_dir, "iceberg_hazard_grid.csv")

    for f in [sic_file, sit_file, ice_file]:
        if not os.path.exists(f):
            print(f"Error: Missing required input file {f}")
            sys.exit(1)

    df_sic = pd.read_csv(sic_file)
    df_sit = pd.read_csv(sit_file)
    df_ice = pd.read_csv(ice_file)
    
    if os.path.exists(iceberg_file):
        df_iceberg = pd.read_csv(iceberg_file)
    else:
        df_iceberg = pd.DataFrame({'latitude': [], 'longitude': [], 'iceberg_presence': [], 'iceberg_distance_km': [], 'iceberg_forecast_time': []})

    gdf_route, corridor_polygon = get_active_corridor()

    merged = pd.merge(df_sic, df_sit[['latitude', 'longitude', 'SIT']], on=['latitude', 'longitude'], how='left')
    merged = pd.merge(merged, df_iceberg[['latitude', 'longitude', 'iceberg_presence', 'iceberg_distance_km', 'iceberg_forecast_time']], on=['latitude', 'longitude'], how='left')
    merged['iceberg_presence'] = merged['iceberg_presence'].fillna(False)
    
    merged['ice_type_match_method'] = 'missing'
    merged['ice_type_match_distance_km'] = np.nan
    merged['ice_type_label'] = pd.Series(dtype='object')
    
    exact_merge = pd.merge(merged[['latitude', 'longitude']], df_ice[['latitude', 'longitude', 'ice_type_label']], on=['latitude', 'longitude'], how='left')
    
    exact_mask = exact_merge['ice_type_label'].notna()
    if exact_mask.any():
        merged.loc[exact_mask, 'ice_type_label'] = exact_merge.loc[exact_mask, 'ice_type_label']
        merged.loc[exact_mask, 'ice_type_match_method'] = 'exact'
        merged.loc[exact_mask, 'ice_type_match_distance_km'] = 0.0
    
    exact_matches = exact_mask.sum()
    
    missing_ice_mask = merged['ice_type_label'].isna()
    nn_matches = 0
    if missing_ice_mask.sum() > 0:
        df_missing = merged[missing_ice_mask].drop(columns=['ice_type_label'])
        gdf_missing = gpd.GeoDataFrame(df_missing, geometry=[Point(xy) for xy in zip(df_missing.longitude, df_missing.latitude)], crs="EPSG:4326")
        gdf_ice_pts = gpd.GeoDataFrame(df_ice, geometry=[Point(xy) for xy in zip(df_ice.longitude, df_ice.latitude)], crs="EPSG:4326")
        
        matched_nn = gpd.sjoin_nearest(
            gdf_missing.to_crs("EPSG:3031"),
            gdf_ice_pts.to_crs("EPSG:3031")[['ice_type_label', 'geometry']],
            how='left',
            max_distance=15000,
            distance_col='match_dist_m'
        )
        
        matched_nn = matched_nn[~matched_nn.index.duplicated(keep='first')]
        
        valid_nn = matched_nn['ice_type_label'].notna()
        nn_new = valid_nn.sum()
        nn_matches = int(nn_new)
        
        valid_indices = matched_nn[valid_nn].index
        merged.loc[valid_indices, 'ice_type_label'] = matched_nn.loc[valid_indices, 'ice_type_label']
        merged.loc[valid_indices, 'ice_type_match_method'] = 'nearest'
        merged.loc[valid_indices, 'ice_type_match_distance_km'] = matched_nn.loc[valid_indices, 'match_dist_m'] / 1000.0
        
    remaining_missing = merged['ice_type_label'].isna().sum()
    matched = merged

    records = []
    for _, row in matched.iterrows():
        sic = row['siconc']
        ice_type = row['ice_type_label']
        sit = row['SIT']
        
        result = classify_cell(sic, ice_type, sit, vessel_class)
        result['latitude'] = row['latitude']
        result['longitude'] = row['longitude']
        result['ice_type_match_method'] = row['ice_type_match_method']
        result['ice_type_match_distance_km'] = row['ice_type_match_distance_km']
        result['iceberg_presence'] = row.get('iceberg_presence', False)
        result['iceberg_distance_km'] = row.get('iceberg_distance_km', np.nan)
        result['iceberg_forecast_time'] = row.get('iceberg_forecast_time', None)
        records.append(result)

    df_out = pd.DataFrame(records)

    # Preserve sea ice risk BEFORE iceberg overrides
    df_out['sea_ice_risk'] = df_out['operational_risk']
    df_out['sea_ice_risk_source'] = df_out['risk_source']
    df_out['iceberg_risk'] = "NONE"

    # Iceberg Risk Override
    if 'iceberg_presence' in df_out.columns:
        hazard_mask = df_out['iceberg_presence'] == True
        if hazard_mask.any():
            df_out.loc[hazard_mask, 'iceberg_risk'] = 'EXTREME'
            df_out.loc[hazard_mask, 'operational_risk'] = 'EXTREME'
            df_out.loc[hazard_mask, 'risk_source'] = 'ICEBERG_COLLISION_ZONE'

    # Unified risk_score
    df_out['risk_score'] = np.nan
    df_out['risk_score_type'] = "UNKNOWN"
    
    for i, row in df_out.iterrows():
        if row['iceberg_presence']:
            df_out.at[i, 'risk_score'] = 100.0
            df_out.at[i, 'risk_score_type'] = "ICEBERG_COLLISION_ZONE"
        elif pd.notna(row['RIO']):
            df_out.at[i, 'risk_score'] = row['RIO']
            df_out.at[i, 'risk_score_type'] = "POLARIS_RIO"
        elif pd.notna(row['DLIRI']):
            df_out.at[i, 'risk_score'] = row['DLIRI']
            df_out.at[i, 'risk_score_type'] = "DLIRI"
        else:
            df_out.at[i, 'risk_score'] = 100.0 * row['SIC']
            df_out.at[i, 'risk_score_type'] = "SIC_ONLY"

    cols = ['latitude', 'longitude', 'SIC', 'SIT', 'Ice_Type', 'Ice_Type_Norm', 'polaris_ice_category',
            'RIO', 'RIV', 'rio_method', 'rio_available', 'DLIRI', 'DLIRI_category', 'effective_thickness', 'thickness_factor',
            'iceberg_presence', 'iceberg_distance_km', 'iceberg_forecast_time', 
            'sea_ice_risk', 'sea_ice_risk_source', 'iceberg_risk', 'risk_score', 'risk_score_type',
            'operational_risk', 'risk_source', 'confidence', 'status', 'fallback_used', 'fallback_reason',
            'ice_type_match_method', 'ice_type_match_distance_km', 'vessel_class', 
            'sit_valid', 'ice_type_missing', 'ice_type_ambiguous']
    df_out = df_out[cols]

    csv_path = os.path.join(run_dir, "polaris_grid.csv")
    df_out.to_csv(csv_path, index=False)
    
    def to_str_arr(series):
        return series.fillna("NaN").to_numpy(dtype=str)

    ds_out = xr.Dataset(
        data_vars={
            'RIO': (['cell'], df_out['RIO'].values),
            'RIV': (['cell'], df_out['RIV'].values),
            'rio_method': (['cell'], to_str_arr(df_out['rio_method'])),
            'rio_available': (['cell'], df_out['rio_available'].values),
            'DLIRI': (['cell'], df_out['DLIRI'].values),
            'SIC': (['cell'], df_out['SIC'].values),
            'SIT': (['cell'], df_out['SIT'].values),
            'effective_thickness': (['cell'], df_out['effective_thickness'].values),
            'thickness_factor': (['cell'], df_out['thickness_factor'].values),
            'Ice_Type': (['cell'], to_str_arr(df_out['Ice_Type'])),
            'Ice_Type_Norm': (['cell'], to_str_arr(df_out['Ice_Type_Norm'])),
            'polaris_ice_category': (['cell'], to_str_arr(df_out['polaris_ice_category'])),
            'operational_risk': (['cell'], to_str_arr(df_out['operational_risk'])),
            'risk_source': (['cell'], to_str_arr(df_out['risk_source'])),
            'confidence': (['cell'], to_str_arr(df_out['confidence'])),
            'status': (['cell'], to_str_arr(df_out['status'])),
            'fallback_used': (['cell'], df_out['fallback_used'].values),
            'fallback_reason': (['cell'], to_str_arr(df_out['fallback_reason'])),
            'ice_type_match_method': (['cell'], to_str_arr(df_out['ice_type_match_method'])),
            'ice_type_match_distance_km': (['cell'], df_out['ice_type_match_distance_km'].values),
            'iceberg_presence': (['cell'], df_out['iceberg_presence'].values),
            'iceberg_distance_km': (['cell'], df_out['iceberg_distance_km'].values),
            'iceberg_forecast_time': (['cell'], to_str_arr(df_out['iceberg_forecast_time'])),
            'sea_ice_risk': (['cell'], to_str_arr(df_out['sea_ice_risk'])),
            'sea_ice_risk_source': (['cell'], to_str_arr(df_out['sea_ice_risk_source'])),
            'iceberg_risk': (['cell'], to_str_arr(df_out['iceberg_risk'])),
            'risk_score': (['cell'], df_out['risk_score'].values),
            'risk_score_type': (['cell'], to_str_arr(df_out['risk_score_type'])),
        },
        coords={
            'latitude': (['cell'], df_out['latitude'].values),
            'longitude': (['cell'], df_out['longitude'].values)
        },
        attrs={'vessel_class': vessel_class}
    )
    nc_path = os.path.join(run_dir, "polaris_grid.nc")
    ds_out.to_netcdf(nc_path)

    tot = len(df_out)
    c_polaris = (df_out['risk_source'] == 'POLARIS').sum()
    c_dliri = (df_out['risk_source'] == 'DLIRI').sum()
    c_siconly = (df_out['risk_source'] == 'SIC_ONLY').sum()
    
    print("\n=================================================================")
    print("FINAL SUMMARY REPORT")
    print("=================================================================")
    print("\nSpatial Matching Statistics:")
    print(f"Total cells                        : {tot}")
    print(f"Exact Ice Type matches             : {exact_matches}")
    print(f"Nearest-neighbour Ice Type matches : {nn_matches}")
    print(f"Remaining missing Ice Type         : {remaining_missing}")

    dist_valid = df_out['ice_type_match_distance_km'].dropna()
    print("\nMatch Distance Statistics (km):")
    if not dist_valid.empty:
        print(f"  Min: {dist_valid.min():.3f} | Mean: {dist_valid.mean():.3f} | Median: {dist_valid.median():.3f} | Max: {dist_valid.max():.3f}")
    else:
        print("  None")

    print("\nPre-Classification Ice Type Distribution:")
    print(df_out['Ice_Type_Norm'].value_counts().to_string())

    print("\nCoverage Statistics:")
    print(f"POLARIS direct       : {(c_polaris - df_out['fallback_used'].sum()):5d}")
    print(f"POLARIS fallback     : {df_out['fallback_used'].sum():5d}")
    print(f"DLIRI                : {c_dliri:5d}")
    print(f"SIC_ONLY             : {c_siconly:5d}")
    print(f"Total operational coverage: {c_polaris + c_dliri + c_siconly} ({100.0 * (c_polaris + c_dliri + c_siconly) / tot:.1f}%)")
    
    cells_with_rio = df_out['RIO'].notna().sum()
    cells_with_riv = df_out['RIV'].notna().sum()
    
    print("\nTotal grid cells                   :", tot)
    print("Cells with iceberg presence        :", df_out['iceberg_presence'].sum())
    print("Cells without iceberg presence     :", tot - df_out['iceberg_presence'].sum())
    print("Cells with genuine POLARIS RIO     :", cells_with_rio)
    print("Cells using DLIRI                  :", c_dliri)
    print("Cells using SIC_ONLY               :", c_siconly)
    print("Final EXTREME iceberg collision cells:", (df_out['risk_source'] == 'ICEBERG_COLLISION_ZONE').sum())
    print("\nFinal risk-source distribution:")
    print(df_out['risk_source'].value_counts().to_string())
    print("\nOne unified final risk grid generated: polaris_grid.csv")

    validate_pipeline(df_out)
    generate_maps(df_out, gdf_route, corridor_polygon, vessel_class, run_dir)

if __name__ == "__main__":
    vessel_class = sys.argv[1] if len(sys.argv) > 1 else "PC4"
    run(vessel_class=vessel_class, run_dir=".")
