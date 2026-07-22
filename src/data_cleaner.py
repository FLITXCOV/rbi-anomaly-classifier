import pandas as pd
import os
import glob

def load_and_merge_quarters(folder_path, log_callback=None):
    """
    Scans the folder for all Excel files. Extracts the 'Period End Date' from each.
    Identifies the 5 most recent quarters. Merges them, filters for '6. TOTAL', 
    calculates absolute cash, and pivots into a horizontal format.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    log("\n--- INITIATING DATA CLEANER (MULTI-QUARTER MODE) ---")
    pd.options.mode.chained_assignment = None

    excel_files = glob.glob(os.path.join(folder_path, "*.xls*")) + glob.glob(os.path.join(folder_path, "*.csv"))
    
    if not excel_files:
        log("ERROR: No valid data files (*.xlsx or *.csv) found in the input folder.")
        return None, None, None

    log(f"Found {len(excel_files)} Excel files. Scanning dates...")

    file_date_map = []
    
    # --- Step 1: Scan all files to find their quarter dates ---
    for file_path in excel_files:
        try:
            is_csv = file_path.lower().endswith('.csv')
            if is_csv:
                df_preview = pd.read_csv(file_path, nrows=5)
            else:
                df_preview = pd.read_excel(file_path, nrows=5)
                
            # Find the 'Period End Date' column
            date_col = next((c for c in df_preview.columns if 'Period End Date' in str(c)), None)
            
            if not date_col:
                # If there's a skip row issue, try reading with skiprows=1
                if is_csv:
                    df_preview = pd.read_csv(file_path, skiprows=1, nrows=5)
                else:
                    df_preview = pd.read_excel(file_path, skiprows=1, nrows=5)
                date_col = next((c for c in df_preview.columns if 'Period End Date' in str(c)), None)
            
            if date_col and not df_preview[date_col].isna().all():
                raw_date = df_preview[date_col].iloc[0]
                parsed_date = pd.to_datetime(raw_date)
                
                # We need to know if this file needs skiprows=1 for full load
                needs_skiprows = False
                # A simple heuristic: if 'Item Desc' or '6. TOTAL' is in the first row without skip, it doesn't need it.
                # But safer to just read the file fully later and check.
                
                file_date_map.append({
                    'path': file_path,
                    'date': parsed_date
                })
        except Exception as e:
            log(f"WARNING: Could not parse date from {os.path.basename(file_path)}. Skipping.")
            continue

    if not file_date_map:
        log("ERROR: Could not find valid 'Period End Date' in any files.")
        return None, None, None

    # Sort files by date descending (newest first)
    file_date_map.sort(key=lambda x: x['date'], reverse=True)
    
    # Pick the 5 most recent
    selected_files = file_date_map[:5]
    selected_files.sort(key=lambda x: x['date']) # Sort back to chronological order (Q1 -> Q5)
    
    if len(selected_files) < 5:
        log(f"WARNING: Only {len(selected_files)} quarter files found with valid dates. Minimum 5 required for Tier 1 Math.")
        # We will proceed anyway, but math might break or be less robust if strictly Q5 logic is hardcoded.
        # However, the strict requirement is 5.
        if len(selected_files) < 2:
             log("ERROR: Not enough quarters to perform analysis.")
             return None, None, None

    log(f"Selected {len(selected_files)} most recent quarters for analysis:")
    for sf in selected_files:
        log(f"  - {sf['date'].strftime('%Y-%m-%d')} ({os.path.basename(sf['path'])})")

    # --- Step 2: Load and Merge ---
    all_totals = []
    raw_dfs = []   # Collects aggregated branch data for Tier 2 diagnostics
    
    for sf in selected_files:
        path = sf['path']
        try:
            # Try loading normally (Universal CSV Support)
            is_csv = path.lower().endswith('.csv')
            if is_csv:
                df = pd.read_csv(path)
                if 'Period End Date' not in df.columns:
                    df = pd.read_csv(path, skiprows=1)
            else:
                df = pd.read_excel(path)
                if 'Period End Date' not in df.columns:
                    df = pd.read_excel(path, skiprows=1)
                
            df.columns = df.columns.astype(str).str.strip()
            
            # ---------------------------------------------------------
            # REAL DATA AGGREGATION ENGINE
            # The real RBI data does not have a pre-calculated '6. TOTAL' row.
            # We must filter for the top-level sector codes (100, 200, 300, 400, 500)
            # and aggregate them to create a total branch row, avoiding sub-categories.
            # ---------------------------------------------------------
            
            # 1. Filter top-level items
            df['Item Code'] = pd.to_numeric(df['Item Code'], errors='coerce')
            top_level = df[df['Item Code'].isin([100, 200, 300, 400, 500])].copy()
            
            if top_level.empty:
                continue
                
            # 2. Extract standard columns safely
            top_level['Period End Date'] = pd.to_datetime(top_level['Period End Date']).dt.strftime('%Y-%m-%d')
            
            if 'Term Amount' in top_level.columns:
                top_level['Term_Cash_Col'] = top_level['Term Amount'].astype(float).fillna(0)
            elif 'Term CD' in top_level.columns and 'Term Other' in top_level.columns:
                top_level['Term_Cash_Col'] = (top_level['Term CD'].astype(float).fillna(0) +
                                              top_level['Term Other'].astype(float).fillna(0))
            else:
                top_level['Term_Cash_Col'] = 0.0

            top_level['Current_Cash_Col'] = top_level['Current Amount'].astype(float).fillna(0)
            top_level['Saving_Cash_Col'] = top_level['Saving Amount'].astype(float).fillna(0)
            
            # --- REDUNDANCY CHECK: Cross-validate against RBI's Total Amount ---
            if 'Total Amount' in top_level.columns:
                rbi_total = top_level['Total Amount'].astype(float).fillna(0)
                our_total = top_level['Current_Cash_Col'] + top_level['Saving_Cash_Col'] + top_level['Term_Cash_Col']
                mismatch = (our_total - rbi_total).abs() > 1.0  # Allow ₹1 rounding tolerance
                mismatch_count = mismatch.sum()
                if mismatch_count > 0:
                    log(f"  ⚠ DATA INTEGRITY WARNING in {os.path.basename(path)}: "
                        f"{mismatch_count} rows where Current+Saving+Term ≠ Total Amount. "
                        f"Max deviation: ₹{(our_total - rbi_total).abs().max():,.0f}")
                else:
                    log(f"  ✓ Redundancy check passed for {os.path.basename(path)} — all rows match Total Amount.")
            
            if 'Part1 Code' in top_level.columns:
                top_level['Branch_Code'] = top_level['Part1 Code'].astype(str).str.strip()
            else:
                log(f"ERROR: Could not find 'Part1 Code' column in {os.path.basename(path)}")
                continue
                
            if 'Population Group Name' in top_level.columns:
                top_level['Pop_Group'] = top_level['Population Group Name'].astype(str).str.strip()
            elif 'Bank Group Name' in top_level.columns:
                top_level['Pop_Group'] = top_level['Bank Group Name'].astype(str).str.strip()
            else:
                top_level['Pop_Group'] = 'Unknown'
                
            # 3. Aggregate to branch level
            agg_funcs = {
                'Current_Cash_Col': 'sum',
                'Saving_Cash_Col': 'sum',
                'Term_Cash_Col': 'sum'
            }
            # Preserve metadata for Tier 2 reporting
            meta_cols = ['Bank Group Name', 'Bank Name', 'Region', 'State', 'District', 'Centre', 'Population Group Name']
            for c in meta_cols:
                if c in top_level.columns:
                    agg_funcs[c] = 'first'
                    
            branch_totals = top_level.groupby(['Branch_Code', 'Pop_Group', 'Period End Date'], as_index=False).agg(agg_funcs)
            
            branch_totals['Total_Cash'] = branch_totals['Current_Cash_Col'] + branch_totals['Saving_Cash_Col'] + branch_totals['Term_Cash_Col']
            
            # For Tier 2 compatibility, we map the aggregated columns back to what Tier 2 expects:
            branch_totals['Item Desc'] = '6. TOTAL'
            branch_totals['Part1 Code'] = branch_totals['Branch_Code']
            branch_totals['Current Amount'] = branch_totals['Current_Cash_Col']
            branch_totals['Saving Amount'] = branch_totals['Saving_Cash_Col']
            branch_totals['Term Amount'] = branch_totals['Term_Cash_Col']
            
            all_totals.append(branch_totals[['Branch_Code', 'Pop_Group', 'Period End Date', 'Total_Cash']])
            raw_dfs.append(branch_totals) # Pass the aggregated branch_totals to Tier 2
            
            # Memory Management
            del df
            
        except Exception as e:
            log(f"ERROR loading {os.path.basename(path)}: {str(e)}")

    if not all_totals:
        log("ERROR: Failed to extract top-level aggregated data from files.")
        return None, None, None

    merged_totals = pd.concat(all_totals, ignore_index=True)
    
    # --- Step 3: Pivot to horizontal layout ---
    clean_df = merged_totals.pivot_table(
        index=['Branch_Code', 'Pop_Group'],
        columns='Period End Date',
        values='Total_Cash',
        aggfunc='sum'
    ).reset_index().set_index('Branch_Code')
    
    # Pop_Group is a text column — exclude it from the numeric quarter list
    dynamic_quarter_cols = sorted([c for c in clean_df.columns.tolist() if c != 'Pop_Group'])
    
    # Final cleanup: drop branches that don't have the target quarter (Q5)
    # The math engine assumes target_col exists
    target_col = dynamic_quarter_cols[-1]
    clean_df = clean_df.dropna(subset=[target_col])
    
    log(f"Cleaned data successfully: {len(clean_df)} unique branches prepared.")
    
    log("Assembling combined raw dataset for Tier 2 diagnostics...")
    if raw_dfs:
        combined_raw_df = pd.concat(raw_dfs, ignore_index=True)
    else:
        combined_raw_df = pd.DataFrame()
    
    return clean_df, dynamic_quarter_cols, combined_raw_df