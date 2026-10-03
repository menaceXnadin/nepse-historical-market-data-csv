import pandas as pd
import os
import glob
from pathlib import Path

def standardize_csv(filepath):
    """
    Read a CSV file and ensure all numeric columns are float64
    to prevent schema inconsistencies
    """
    try:
        # Read CSV
        df = pd.read_csv(filepath)
        
        # Define the expected schema with consistent types
        dtype_map = {
            'time': str,
            'symbol': str,
            'open': float,
            'close': float,
            'high': float,
            'low': float,
            'volume': int,
            'category': str
        }
        
        # Convert columns to the correct types
        for col, dtype in dtype_map.items():
            if col in df.columns:
                if dtype == float:
                    df[col] = df[col].astype('float64')
                elif dtype == int:
                    df[col] = df[col].astype('int64')
                elif dtype == str:
                    df[col] = df[col].astype(str)
        
        # Write back to CSV with consistent formatting
        df.to_csv(filepath, index=False)
        return True, None
    except Exception as e:
        return False, str(e)

def main():
    # Find all CSV files in data directory
    csv_patterns = [
        'data/stock/adjusted/*.csv',
        'data/stock/unadjusted/*.csv',
        'data/index/adjusted/*.csv',
        'data/index/unadjusted/*.csv',
        'data/subindices/adjusted/*.csv',
        'data/subindices/unadjusted/*.csv'
    ]
    
    all_files = []
    for pattern in csv_patterns:
        all_files.extend(glob.glob(pattern))
    
    print(f"Found {len(all_files)} CSV files to process")
    
    success_count = 0
    error_count = 0
    
    for i, filepath in enumerate(all_files, 1):
        success, error = standardize_csv(filepath)
        if success:
            success_count += 1
            if i % 50 == 0:
                print(f"Processed {i}/{len(all_files)} files...")
        else:
            error_count += 1
            print(f"Error processing {filepath}: {error}")
    
    print(f"\n{'='*60}")
    print(f"Processing complete!")
    print(f"Successfully standardized: {success_count} files")
    print(f"Errors: {error_count} files")
    print(f"{'='*60}")
    print("\nAll numeric columns (open, close, high, low) are now float64")
    print("Volume column is int64")
    print("String columns (time, symbol, category) are string type")

if __name__ == "__main__":
    main()
