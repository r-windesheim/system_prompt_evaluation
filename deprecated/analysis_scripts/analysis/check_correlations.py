#!/usr/bin/env python3
"""Quick script to check dimension correlations"""
import pandas as pd
import numpy as np
from config import EVALUATION_DIMENSIONS, BATCH_EVALUATION_FILE

# Load data
df = pd.read_csv(BATCH_EVALUATION_FILE)

# Build dimension matrix
configs = df['config_name'].unique()
configs = [c for c in configs if c and str(c) != 'nan']

dimension_matrix = []
for config in configs:
    row = {'config': config}
    config_data = df[df['config_name'] == config]

    for dim in EVALUATION_DIMENSIONS:
        dim_keyword = dim.replace('_', ' ')
        dim_data = config_data[
            config_data['evaluation_question'].str.contains(dim_keyword, case=False, na=False)
        ]
        if len(dim_data) > 0:
            row[dim] = dim_data['evaluation_score'].mean()
        else:
            row[dim] = np.nan

    dimension_matrix.append(row)

dm = pd.DataFrame(dimension_matrix)

# Calculate correlation matrix
print('\nCorrelation Matrix:')
print(dm[EVALUATION_DIMENSIONS].corr().round(3))
print()

# Show score ranges
print('Score Ranges by Dimension:')
for dim in EVALUATION_DIMENSIONS:
    scores = dm[dim].dropna()
    print(f'{dim:25s} | Min: {scores.min():.1f} | Max: {scores.max():.1f} | Range: {scores.max()-scores.min():.1f} | Std: {scores.std():.1f}')

print()
print('Overall Statistics:')
print(f'Total configs: {len(dm)}')
print(f'Completeness: {dm[EVALUATION_DIMENSIONS].notna().sum().sum()}/{len(dm)*len(EVALUATION_DIMENSIONS)}')
