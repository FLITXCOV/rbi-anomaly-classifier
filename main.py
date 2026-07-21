import pandas as pd
import os
import warnings

# Import the data cleaning and anomaly engines
from src.data_cleaner import load_and_merge_quarters
from src.anomaly_math import run_tier1_engine, run_tier2_engine

# Mute harmless Excel styling warnings
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

OUTPUT_FULL_LIST = "data/02_app_output/Tier1_Flagged_Anomalies.xlsx"
OUTPUT_TOP10     = "data/02_app_output/Top10_Audit_Report.xlsx"


def run_pipeline(input_folder: str, log_callback=None):
    """
    Core pipeline: load -> clean -> Tier 1 -> Tier 2 -> export.

    Args:
        input_folder: Absolute or relative path to the folder containing raw Excel files.
        log_callback: Optional callable(str) that receives log messages in real time.
                      If None, messages are printed to stdout (command-line mode).

    Returns:
        dict with result data, or None if the pipeline failed.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    os.makedirs(os.path.dirname(OUTPUT_FULL_LIST), exist_ok=True)

    if not os.path.exists(input_folder):
        log(f"ERROR: Could not find input folder: {input_folder}")
        return None

    log(f"Scanning folder for quarter files: {input_folder}")

    # --- ETL ---
    clean_df, dynamic_quarter_cols, combined_raw_df = load_and_merge_quarters(input_folder, log_callback)
    if clean_df is None:
        log("ERROR: Data cleaning failed. Check the raw file format.")
        return None

    # --- Tier 1 ---
    flagged_df = run_tier1_engine(clean_df, dynamic_quarter_cols)
    total_branches = len(clean_df)

    log(f"\n--- TIER 1 SUMMARY ---")
    log(f"Total flagged: {len(flagged_df)} / {total_branches} branches")
    if len(flagged_df) == 0:
        log("WARNING: 0 branches flagged. Check anomaly_math.py configuration.")
        return None

    log(f"Severity Score range: {flagged_df['Severity_Score'].min():.2f} to {flagged_df['Severity_Score'].max():.2f}")
    log("Flagged branches by peer group (size decile):")
    for grp, cnt in flagged_df['Peer_Group'].value_counts().items():
        log(f"  Group {grp}: {cnt} branches")

    # --- Tier 2 ---
    flagged_export = flagged_df.copy()
    flagged_export.reset_index(inplace=True)
    flagged_export = run_tier2_engine(flagged_export, combined_raw_df, dynamic_quarter_cols)

    cause_summary = flagged_export['Root_Cause'].apply(
        lambda x: x.split(' (')[0] if '(' in x else x
    ).value_counts()
    log("\nRoot Cause Distribution:")
    for cause, count in cause_summary.items():
        log(f"  {cause}: {count} branches")

    # --- Format for export ---
    account_cols = []
    for acc in ['Current', 'Savings', 'Term']:
        for q in dynamic_quarter_cols:
            account_cols.append(f"{acc}_{q}")

    log("\nFormatting cash values into Crores...")
    all_rupee_cols = dynamic_quarter_cols + account_cols
    for col in all_rupee_cols:
        if col in flagged_export.columns:
            flagged_export[col] = (flagged_export[col] / 10000000).round(0).astype(int)

    rename_dict = {col: f"{col} (Crores)" for col in all_rupee_cols if col in flagged_export.columns}
    flagged_export.rename(columns=rename_dict, inplace=True)

    # --- Export Excel files ---
    flagged_export.to_excel(OUTPUT_FULL_LIST, index=False)
    log(f"\nSaved full anomaly list ({len(flagged_export)} branches) to: {OUTPUT_FULL_LIST}")

    top10_df = flagged_export.head(10).copy()
    top10_df.to_excel(OUTPUT_TOP10, index=False)
    log(f"Saved Top 10 executive report to: {OUTPUT_TOP10}")
    log("\n✓ Engine Complete.")

    return {
        'flagged_df'    : flagged_export,
        'total_branches': total_branches,
        'flagged_count' : len(flagged_export),
        'severity_max'  : flagged_df['Severity_Score'].max(),
        'severity_min'  : flagged_df['Severity_Score'].min(),
        'quarter_cols'  : dynamic_quarter_cols,
        'output_full'   : os.path.abspath(OUTPUT_FULL_LIST),
        'output_top10'  : os.path.abspath(OUTPUT_TOP10),
    }


# --- Command-line entry point (unchanged behaviour) ---------------------------
if __name__ == "__main__":
    INPUT_FOLDER = "data/01_raw_input"
    print("\n--- BOOTING RBI ANOMALY CLASSIFIER (TIER 1 + TIER 2) ---")
    run_pipeline(INPUT_FOLDER)
    print("--------------------------------------\n")
