import pandas as pd
import numpy as np

# =============================================================================
# ----------------------------- CONFIGURATION ---------------------------------
# =============================================================================

# --- TIER 1: MACRO ANOMALY CONFIG (TUKEY'S IQR METHOD) ---
TUKEY_MULTIPLIER = 3.0     # 3.0 = "Extreme Outlier" in standard statistical theory. 
                           # (1.5 is a "Mild Outlier"). Matches strict RBI risk appetite.
MIN_PEER_GROUP_SIZE = 30   # Prevents statistical breakdown in tiny sample sizes.
N_SIZE_BUCKETS = 10        # Decile grouping for apples-to-apples comparison.
IQR_FLOOR = 0.0005         # STATISTICAL SAFEGUARD: Prevents division-by-zero in 
                           # dormant peer groups (The "Invisible Awakening" fix).

# --- TIER 2: ACCOUNT-TYPE ROOT CAUSE DIAGNOSTICS CONFIG ---
ACCOUNT_TYPES = ['Current', 'Savings', 'Term']

# =============================================================================
# ----------------------- TIER 1: MACRO ANOMALY ENGINE ------------------------
# =============================================================================

def _assign_peer_groups(df):
    """Hybrid Bucketing: First by Pop_Group, then by Size Deciles."""
    peer_group_series = pd.Series(index=df.index, dtype=str)
    
    # 1. Stratify by Geographic/Population Group
    for pop_group, subset in df.groupby('Pop_Group'):
        # 2. Stratify by Size within the Population Group
        if len(subset) < MIN_PEER_GROUP_SIZE:
            peer_group_series.loc[subset.index] = f"{pop_group}_All"
            continue
            
        try:
            size_labels = pd.qcut(subset['Mean_Share'], q=N_SIZE_BUCKETS, labels=False, duplicates='drop')
            hybrid_labels = pop_group + "_Bucket_" + size_labels.astype(str)
            peer_group_series.loc[subset.index] = hybrid_labels
        except Exception:
            peer_group_series.loc[subset.index] = f"{pop_group}_All"

    # 3. Clean up tiny resulting buckets
    counts = peer_group_series.value_counts()
    tiny_groups = counts[counts < MIN_PEER_GROUP_SIZE].index
    peer_group_series = peer_group_series.where(~peer_group_series.isin(tiny_groups), 'MERGED_SMALL_GROUPS')
    
    return peer_group_series

def apply_tukey_iqr(shift_series, group_series):
    """
    Applies John Tukey's Interquartile Range (IQR) method for Extreme Outliers.
    This replaces the Z-score with established, textbook statistical theory.
    """
    # 1. Calculate Q3 (75th Percentile) and Q1 (25th Percentile) per group
    q3 = shift_series.groupby(group_series).transform(lambda x: x.quantile(0.75))
    q1 = shift_series.groupby(group_series).transform(lambda x: x.quantile(0.25))
    
    # 2. Calculate IQR and apply the floor to prevent divide-by-zero in dormant groups
    iqr = q3 - q1
    iqr_safe = iqr.clip(lower=IQR_FLOOR)
    
    # 3. Calculate Tukey's Upper Fence for Extreme Outliers
    upper_fence = q3 + (TUKEY_MULTIPLIER * iqr_safe)
    
    # 4. Determine if the branch broke the mathematical fence
    is_stat_anomaly = shift_series > upper_fence
    
    # 5. Calculate Severity Score (How many IQRs beyond Q3 it is) for ranking
    severity_score = (shift_series - q3) / iqr_safe
    
    return is_stat_anomaly, severity_score.fillna(0)

def run_tier1_engine(df, quarter_cols):
    """Tier 1 Engine: Peer-Group Robust Shares using Tukey's IQR Method."""
    print("\n--- INITIATING TIER 1 ENGINE (TUKEY IQR SHARES METHOD) ---")

    type1_df = df.copy()
    for col in quarter_cols:
        type1_df = type1_df[type1_df[col] > 0]
    
    print(f"Filtered for Type 1 (Full History): {len(type1_df)} branches remain.")

    # Convert absolute cash to Market Share %
    shares_df = pd.DataFrame(index=type1_df.index)
    for col in quarter_cols:
        total_bank_deposit = type1_df[col].sum()
        shares_df[col] = (type1_df[col] / total_bank_deposit) * 100

    history_cols = quarter_cols[:-1]
    target_col = quarter_cols[-1]

    # Calculate Deltas
    type1_df['Mean_Share'] = shares_df[history_cols].mean(axis=1)
    type1_df['Target_Share'] = shares_df[target_col]
    type1_df['Share_Shift'] = (type1_df['Target_Share'] - type1_df['Mean_Share']).abs()

    # Assign Peer Groups
    type1_df['Peer_Group'] = _assign_peer_groups(type1_df)

    # Apply Tukey's Statistical Theory
    is_stat_anomaly, severity = apply_tukey_iqr(type1_df['Share_Shift'], type1_df['Peer_Group'])
    type1_df['Severity_Score'] = severity

    # Final Flag: purely statistical — branch must exceed Q3 + 3×IQR within its peer group
    type1_df['Is_Anomaly'] = is_stat_anomaly

    flagged_branches = type1_df[type1_df['Is_Anomaly']].copy()
    
    # Sort by Statistical Severity to bubble the most violent shocks to the Top 10
    flagged_branches = flagged_branches.sort_values(by='Severity_Score', ascending=False)

    print(f"Successfully isolated {len(flagged_branches)} anomalous branches.")
    return flagged_branches

# =============================================================================
# -------- TIER 2: ACCOUNT-TYPE ROOT CAUSE DIAGNOSTICS ENGINE -----------------
# =============================================================================
#
# PURPOSE: For every branch flagged by Tier 1, this engine drills into the
# branch's internal composition (Current / Savings / Term deposits) to
# identify WHICH account type drove the anomalous shift.
#
# HOW IT WORKS:
#   1. For each flagged branch, extract its Current, Savings, and Term deposit
#      values across all quarters from the raw data.
#   2. For each account type, calculate:
#      a) The ABSOLUTE deviation: how much the target quarter's rupee value
#         deviated from the historical median (in rupees).
#      b) The COMPOSITION deviation: how much the account type's share of
#         the branch's total deposits shifted (in percentage points).
#   3. A "Dual Signal" validation requires BOTH absolute rupee materiality
#      AND composition shift to confirm a root cause. This prevents false
#      attribution to account types that moved in rupees but stayed the same
#      proportion of the branch.
#   4. If no single account type passes both tests, the branch is labeled
#      "Systemic (Internal Structure Normal)" — meaning the entire branch
#      shifted uniformly, not driven by any one deposit type.
# =============================================================================

def _diagnose_one_branch(row, history_cols, target_col):
    """
    Diagnoses internal DNA shifts for a single branch using a purely statistical Robust Z-Score.
    
    For each account type (Current, Savings, Term):
      - Calculates the historical median and Median Absolute Deviation (MAD).
      - Calculates the Robust Z-Score (Modified Z-Score).
      - If the Z-Score is > 3.0, it is flagged as an Extreme Statistical Outlier.
    
    Returns:
        root_cause_label (str): e.g., "Current (Robust Z-Score: 4.23)" or "Systemic (Internal Structure Normal)"
        diag (dict): Full diagnostic details for each account type.
    """
    account_types = ['Current', 'Savings', 'Term']

    diag = {}
    for acc in account_types:
        # Extract the raw rupee values for this account type across all quarters
        hist_rupees = np.array([row.get(f'{acc}_{col}', 0) for col in history_cols])
        target_rupees = row.get(f'{acc}_{target_col}', 0)

        # Calculate the historical median and MAD (Median Absolute Deviation)
        median_rupees = np.median(hist_rupees)
        mad_rupees = np.median(np.abs(hist_rupees - median_rupees))
        
        # Statistical safeguard: prevent division by zero in perfectly flat account types
        # 1% of median is a safe baseline for minimum volatility
        mad_rupees_safe = max(mad_rupees, 0.01 * median_rupees, 1.0)
        
        deviation_rupees = abs(target_rupees - median_rupees)
        
        # Robust Z-Score formula (Modified Z-Score by Iglewicz and Hoaglin)
        # 0.6745 normalizes MAD to match standard deviation
        robust_z_score = 0.6745 * deviation_rupees / mad_rupees_safe

        # SIGNAL: Must be an extreme statistical outlier (> 3.0)
        is_outlier = robust_z_score > 3.0

        diag[acc] = {
            'Robust_Z_Score': round(robust_z_score, 2),
            'Deviation_Rupees': round(deviation_rupees, 2),
            'Is_Outlier': is_outlier,
        }

    # --- Determine root cause from candidates that passed the statistical test ---
    candidates = {a: d for a, d in diag.items() if d['Is_Outlier']}
    if not candidates:
        root_cause_label = "Systemic (Internal Structure Normal)"
        direction = "N/A"
    else:
        # Pick the account type with the highest absolute deviation as the primary driver
        root_cause = max(candidates, key=lambda a: candidates[a]['Deviation_Rupees'])
        root_cause_label = f"{root_cause} (Robust Z-Score: {candidates[root_cause]['Robust_Z_Score']})"

        # Determine direction: did Q5 go above or below the historical median?
        hist_rupees = np.array([row.get(f'{root_cause}_{col}', 0) for col in history_cols])
        median_rupees = np.median(hist_rupees)
        target_rupees = row.get(f'{root_cause}_{target_col}', 0)
        direction = "Surge" if target_rupees > median_rupees else "Collapse"

    return root_cause_label, direction, diag


def run_tier2_engine(flagged_df, raw_df, quarter_cols):
    """
    Tier 2 Engine: Account-Type Root Cause Diagnostics.
    
    For every branch flagged by Tier 1, this drills into the raw data to
    determine which account type (Current, Savings, or Term) drove the anomaly.
    
    Args:
        flagged_df (pd.DataFrame): ALL branches flagged by Tier 1 (must have 'Branch_Code' column).
        raw_df (pd.DataFrame): The original raw ledger DataFrame (before cleaning).
        quarter_cols (list): Sorted list of quarter date strings.
    
    Returns:
        pd.DataFrame: flagged_df with a new 'Root_Cause' column appended.
    """
    print("\n--- INITIATING TIER 2 ENGINE (ACCOUNT-TYPE ROOT CAUSE DIAGNOSTICS) ---")

    history_cols = quarter_cols[:-1]
    target_col = quarter_cols[-1]

    # --- Step 1: Extract account-type-level data from raw ledger ---
    # Filter for '6. TOTAL' rows only (same filter as data_cleaner.py)
    wide = raw_df[raw_df['Item Desc'].astype(str).str.contains('6. TOTAL', case=False, na=False)].copy()
    wide['Period End Date'] = pd.to_datetime(wide['Period End Date']).dt.strftime('%Y-%m-%d')
    wide['Branch_Code'] = wide['Part1 Code'].astype(str).str.strip()

    # --- Step 2: Handle Term column naming conventions ---
    # New format (Book1.xlsx): 'Term Amount' is a single pre-merged column.  <- CURRENT
    # Legacy format:           'Term CD' + 'Term Other' (two separate cols)  <- OLD
    # The block below handles both so old test files still work.
    if 'Term Amount' in wide.columns:
        pass  # Already correct — new format, nothing to do
    elif 'Term CD' in wide.columns and 'Term Other' in wide.columns:
        wide['Term Amount'] = (
            wide['Term CD'].astype(float).fillna(0) +
            wide['Term Other'].astype(float).fillna(0)
        )
    else:
        print("WARNING: Could not find Term columns for Tier 2 analysis. Defaulting to 0.")
        wide['Term Amount'] = 0.0

    # --- Step 3: Pivot each account type into a wide format ---
    # Maps our internal account type names to the confirmed new-format column names.
    # 'Saving Amount' (no trailing 's') is per the official RBI BSR 2 column naming.
    column_mapping = {
        'Current': 'Current Amount',
        'Savings': 'Saving Amount',   # RBI column name: 'Saving Amount' (no 's') — confirmed in new format
        'Term':    'Term Amount'      # Pre-merged single column in new format
    }

    pivot_frames = {}
    for acc_name, raw_col_name in column_mapping.items():
        if raw_col_name not in wide.columns:
            print(f"WARNING: Column '{raw_col_name}' not found in raw data. Skipping {acc_name}.")
            continue
        p = wide.pivot_table(
            index='Branch_Code', 
            columns='Period End Date',
            values=raw_col_name, 
            aggfunc='sum'
        )
        # Prefix column names with account type for easy lookup: e.g., 'Current_2025-03-31'
        p.columns = [f'{acc_name}_{c}' for c in p.columns]
        pivot_frames[acc_name] = p

    # Combine all account-type pivots into one wide DataFrame
    account_wide = pd.concat(pivot_frames.values(), axis=1).fillna(0)

    # --- Step 4: Diagnose each flagged branch ---
    root_causes = []
    directions = []
    diagnosed_count = 0
    not_found_count = 0

    for _, flag_row in flagged_df.iterrows():
        branch_code = str(flag_row['Branch_Code'])
        if branch_code not in account_wide.index:
            root_causes.append("Data Not Found")
            directions.append("N/A")
            not_found_count += 1
            continue
        branch_data = account_wide.loc[branch_code]
        label, direction, _ = _diagnose_one_branch(branch_data, history_cols, target_col)
        root_causes.append(label)
        directions.append(direction)
        diagnosed_count += 1

    # --- Step 5: Attach root cause and direction to the flagged DataFrame ---
    result_df = flagged_df.copy()
    result_df['Root_Cause'] = root_causes
    result_df['Direction'] = directions

    # Merge the raw account data (Current, Savings, Term across all quarters) onto the final output
    # account_wide's index is Branch_Code, so we merge on that
    result_df = result_df.merge(account_wide, on='Branch_Code', how='left')

    # --- Step 6: Attach Geographical & Institutional Metadata ---
    # The new raw data format contains rich metadata. We extract it once per branch and staple it to the output.
    meta_cols = [
        'Branch_Code', 'Bank Group Name', 'Bank Name', 
        'Region', 'State', 'District', 'Centre', 'Population Group Name'
    ]
    # Filter wide to just the columns that actually exist in the data to be safe
    available_meta = [c for c in meta_cols if c in wide.columns]
    
    if len(available_meta) > 1: # More than just Branch_Code
        # Drop duplicates to get one row of metadata per branch
        branch_meta = wide[available_meta].drop_duplicates(subset=['Branch_Code'])
        result_df = result_df.merge(branch_meta, on='Branch_Code', how='left')

        # Reorder columns to put metadata immediately after Branch_Code and Peer_Group
        cols = result_df.columns.tolist()
        first_cols = ['Branch_Code', 'Peer_Group', 'Is_Anomaly', 'Severity_Score', 'Root_Cause', 'Direction']
        
        # Insert metadata columns right after the core stats
        meta_to_insert = [c for c in available_meta if c != 'Branch_Code']
        
        remaining_cols = [c for c in cols if c not in first_cols and c not in meta_to_insert]
        new_order = [c for c in first_cols if c in cols] + meta_to_insert + remaining_cols
        
        result_df = result_df[new_order]

    print(f"Diagnosed root cause for {diagnosed_count} branches.")
    if not_found_count > 0:
        print(f"WARNING: {not_found_count} branches had no account-level data in raw ledger.")

    # Print summary of root cause distribution
    cause_summary = result_df['Root_Cause'].apply(
        lambda x: x.split(' (')[0] if '(' in x else x
    ).value_counts()
    print(f"\nRoot Cause Distribution:")
    for cause, count in cause_summary.items():
        print(f"  {cause}: {count} branches")

    return result_df