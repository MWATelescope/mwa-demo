#!/bin/bash

# Script to compare calibration quality metrics across different 
# elevation and source distance cutoff configurations

OBSID=$1
DATADIR=${2:-/data/curtin_mwaeor/dev/$OBSID}

if [ -z "$OBSID" ]; then
    echo "Usage: $0 <obsid> [data_dir]"
    echo "Example: $0 1274010302"
    echo "         $0 1274010302 /path/to/data"
    exit 1
fi

python3 - "$OBSID" "$DATADIR" << 'PYPROG'
import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
import re

obsid = sys.argv[1]
datadir = Path(sys.argv[2])

print(f"Analyzing calibration results for {obsid} in {datadir}\n")

# Find all configuration combinations
phase_fits_files = sorted(datadir.glob(f"{obsid} hyp_soln_sdc*_el*_t000_phase_fits.tsv"))
json_files = sorted(datadir.glob(f"hyp_soln_{obsid}_kr_*_sdc*_el*.json"))

# Extract configuration from filenames
def extract_config(filename, pattern):
    """Extract sdc and el values from filename"""
    match = re.search(r'sdc(\d+)_el(\d+)', str(filename))
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None

# Collect metrics from phase_fits.tsv files
phase_metrics = {}
for tsv_file in phase_fits_files:
    sdc, el = extract_config(tsv_file, 'phase_fits')
    if sdc is None:
        continue
    
    try:
        df = pd.read_csv(tsv_file, sep='\t')
        
        # Filter out flagged/bad receivers
        valid = df[df['flag'] == 0]
        
        metrics = {
            'n_receivers': len(valid),
            'mean_chi2dof_xx': valid['chi2dof_xx'].mean(),
            'mean_chi2dof_yy': valid['chi2dof_yy'].mean(),
            'mean_quality_xx': valid['quality_xx'].mean(),
            'mean_quality_yy': valid['quality_yy'].mean(),
            'mean_sigma_resid_xx': valid['sigma_resid_xx'].mean(),
            'mean_sigma_resid_yy': valid['sigma_resid_yy'].mean(),
            'n_outliers_xx': valid['outlier_xx'].sum(),
            'n_outliers_yy': valid['outlier_yy'].sum(),
        }
        phase_metrics[(sdc, el)] = metrics
    except Exception as e:
        print(f"Warning: Could not read {tsv_file.name}: {e}")

# Collect metrics from visqa JSON files
json_metrics = {}
for json_file in json_files:
    sdc, el = extract_config(json_file, 'json')
    if sdc is None:
        continue
    
    try:
        with open(json_file) as f:
            data = json.load(f)
        
        metrics = {
            'percent_unused_bls': data.get('PERCENT_UNUSED_BLS', np.nan),
            'percent_bad_ants': data.get('PERCENT_BAD_ANTS', np.nan),
            'percent_nonconverged': data.get('PERCENT_NONCONVERGED_CHS', np.nan),
            'rms_convergence': data.get('RMS_CONVERGENCE', np.nan),
            'skewness': data.get('SKEWNESS', np.nan),
            'receiver_var': data.get('RECEIVER_VAR', np.nan),
            'n_bad_ants': len(data.get('BAD_ANTS', [])),
        }
        json_metrics[(sdc, el)] = metrics
    except Exception as e:
        print(f"Warning: Could not read {json_file.name}: {e}")

# Combine all metrics
all_configs = sorted(set(phase_metrics.keys()) | set(json_metrics.keys()))

rows = []
for sdc, el in all_configs:
    row = {'sdc': sdc, 'el': el}
    
    # Add phase_fits metrics
    if (sdc, el) in phase_metrics:
        row.update(phase_metrics[(sdc, el)])
    else:
        row.update({
            'n_receivers': np.nan,
            'mean_chi2dof_xx': np.nan,
            'mean_chi2dof_yy': np.nan,
            'mean_quality_xx': np.nan,
            'mean_quality_yy': np.nan,
            'mean_sigma_resid_xx': np.nan,
            'mean_sigma_resid_yy': np.nan,
            'n_outliers_xx': np.nan,
            'n_outliers_yy': np.nan,
        })
    
    # Add JSON metrics
    if (sdc, el) in json_metrics:
        row.update(json_metrics[(sdc, el)])
    else:
        row.update({
            'percent_unused_bls': np.nan,
            'percent_bad_ants': np.nan,
            'percent_nonconverged': np.nan,
            'rms_convergence': np.nan,
            'skewness': np.nan,
            'receiver_var': np.nan,
            'n_bad_ants': np.nan,
        })
    
    rows.append(row)

# Create DataFrame
summary_df = pd.DataFrame(rows)

# Format output
print("="*120)
print(f"CALIBRATION QUALITY SUMMARY FOR OBSID {obsid}")
print("="*120)
print()

# Find best configuration (highest combined quality, lowest chi2dof deviation from 1)
summary_df['quality_avg'] = (summary_df['mean_quality_xx'] + summary_df['mean_quality_yy']) / 2
summary_df['chi2dof_avg'] = (summary_df['mean_chi2dof_xx'] + summary_df['mean_chi2dof_yy']) / 2
summary_df['chi2dof_penalty'] = np.abs(summary_df['chi2dof_avg'] - 1.0)
summary_df['score'] = summary_df['quality_avg'] - summary_df['chi2dof_penalty']

best_idx = summary_df['score'].idxmax()
best_config = summary_df.loc[best_idx]

print(f"RECOMMENDED CONFIGURATION: sdc={int(best_config['sdc'])}_el{int(best_config['el'])}")
print(f"  Quality: XX={best_config['mean_quality_xx']:.4f}, YY={best_config['mean_quality_yy']:.4f}")
print(f"  Chi2/dof: XX={best_config['mean_chi2dof_xx']:.6f}, YY={best_config['mean_chi2dof_yy']:.6f}")
print(f"  RMS Convergence: {best_config['rms_convergence']:.6e}")
print(f"  Bad Antennas: {best_config['percent_bad_ants']:.2f}%")
print()

# Display by elevation limit
for el in sorted(summary_df['el'].unique()):
    el_data = summary_df[summary_df['el'] == el].sort_values('sdc')
    print(f"\nElevation Limit: {el} degrees")
    print("-"*120)
    
    # Show key metrics in a compact format
    display_cols = [
        'sdc', 'n_receivers', 'mean_quality_xx', 'mean_quality_yy',
        'mean_chi2dof_xx', 'mean_chi2dof_yy', 'percent_unused_bls',
        'percent_bad_ants', 'rms_convergence', 'receiver_var'
    ]
    
    print(el_data[display_cols].to_string(index=False))

# Save full table to file
output_file = datadir / f"{obsid}_cal_comparison.tsv"
summary_df.to_csv(output_file, sep='\t', index=False, float_format='%.6f')
print(f"\n\nFull comparison table saved to: {output_file}")

# Print recommendations
print("\n" + "="*120)
print("INTERPRETATION GUIDE")
print("="*120)
print("""
Key Metrics:
- n_receivers: Number of valid receivers used in calibration
- mean_quality_xx/yy: Quality of phase fits (higher is better, range 0-1)
- mean_chi2dof_xx/yy: Reduced chi-squared of fits (should be ~1.0)
- percent_unused_bls: Percentage of baselines not used (lower is better)
- percent_bad_ants: Percentage of bad antennas flagged (lower is better)
- rms_convergence: RMS convergence of calibration (lower is better)
- receiver_var: Variance across receivers (lower is better)

Configuration Parameters:
- sdc: Source distance cutoff in degrees
- el: Elevation limit in degrees

Generally:
- Higher elevation limits reduce ionospheric effects but may reduce number of sources
- Lower source distance cutoffs focus on nearby sources but may reduce calibration sources
- Look for configurations with high quality, low chi2dof (~1), low bad antenna percentage
""")

# Generate plots
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    
    print("\n" + "="*120)
    print("GENERATING PLOTS")
    print("="*120)
    
    # Create figure with subplots - add more width spacing for legends
    fig = plt.figure(figsize=(18, 12))
    gs = GridSpec(3, 2, figure=fig, hspace=0.3, wspace=0.4)
    
    # Get unique values
    sdcs = sorted(summary_df['sdc'].unique())
    els = sorted(summary_df['el'].unique())
    
    # Plot 1: Quality scores heatmap (XX)
    ax1 = fig.add_subplot(gs[0, 0])
    pivot_quality_xx = summary_df.pivot(index='el', columns='sdc', values='mean_quality_xx')
    vmin_xx = np.nanmin(pivot_quality_xx.values)
    vmax_xx = np.nanmax(pivot_quality_xx.values)
    im1 = ax1.imshow(pivot_quality_xx.values, aspect='auto', cmap='RdYlGn', vmin=vmin_xx, vmax=vmax_xx)
    ax1.set_xticks(range(len(sdcs)))
    ax1.set_xticklabels(sdcs)
    ax1.set_yticks(range(len(els)))
    ax1.set_yticklabels(els)
    ax1.set_xlabel('Source Distance Cutoff (degrees)')
    ax1.set_ylabel('Elevation Limit (degrees)')
    ax1.set_title('Mean Quality Score (XX)')
    plt.colorbar(im1, ax=ax1, label='Quality')
    
    # Find best (max) quality
    best_xx_flat = np.nanargmax(pivot_quality_xx.values)
    best_xx_i, best_xx_j = np.unravel_index(best_xx_flat, pivot_quality_xx.values.shape)
    
    # Add values to heatmap and highlight best
    for i in range(len(els)):
        for j in range(len(sdcs)):
            val = pivot_quality_xx.iloc[i, j]
            if not np.isnan(val):
                color = 'white' if val < 0.5 else 'black'
                ax1.text(j, i, f'{val:.3f}', ha='center', va='center', color=color, fontsize=8)
                # Highlight best value with pink border
                if i == best_xx_i and j == best_xx_j:
                    from matplotlib.patches import Rectangle
                    rect = Rectangle((j-0.5, i-0.5), 1, 1, linewidth=3, edgecolor='magenta', facecolor='none')
                    ax1.add_patch(rect)
    
    # Plot 2: Quality scores heatmap (YY)
    ax2 = fig.add_subplot(gs[0, 1])
    pivot_quality_yy = summary_df.pivot(index='el', columns='sdc', values='mean_quality_yy')
    vmin_yy = np.nanmin(pivot_quality_yy.values)
    vmax_yy = np.nanmax(pivot_quality_yy.values)
    im2 = ax2.imshow(pivot_quality_yy.values, aspect='auto', cmap='RdYlGn', vmin=vmin_yy, vmax=vmax_yy)
    ax2.set_xticks(range(len(sdcs)))
    ax2.set_xticklabels(sdcs)
    ax2.set_yticks(range(len(els)))
    ax2.set_yticklabels(els)
    ax2.set_xlabel('Source Distance Cutoff (degrees)')
    ax2.set_ylabel('Elevation Limit (degrees)')
    ax2.set_title('Mean Quality Score (YY)')
    plt.colorbar(im2, ax=ax2, label='Quality')
    
    # Find best (max) quality
    best_yy_flat = np.nanargmax(pivot_quality_yy.values)
    best_yy_i, best_yy_j = np.unravel_index(best_yy_flat, pivot_quality_yy.values.shape)
    
    # Add values to heatmap and highlight best
    for i in range(len(els)):
        for j in range(len(sdcs)):
            val = pivot_quality_yy.iloc[i, j]
            if not np.isnan(val):
                color = 'white' if val < 0.5 else 'black'
                ax2.text(j, i, f'{val:.3f}', ha='center', va='center', color=color, fontsize=8)
                # Highlight best value with pink border
                if i == best_yy_i and j == best_yy_j:
                    from matplotlib.patches import Rectangle
                    rect = Rectangle((j-0.5, i-0.5), 1, 1, linewidth=3, edgecolor='magenta', facecolor='none')
                    ax2.add_patch(rect)
    
    # Plot 3: Chi2/dof heatmap (XX)
    ax3 = fig.add_subplot(gs[1, 0])
    pivot_chi2_xx = summary_df.pivot(index='el', columns='sdc', values='mean_chi2dof_xx')
    vmin_chi2_xx = np.nanmin(pivot_chi2_xx.values)
    vmax_chi2_xx = np.nanmax(pivot_chi2_xx.values)
    im3 = ax3.imshow(pivot_chi2_xx.values, aspect='auto', cmap='RdYlGn_r', vmin=vmin_chi2_xx, vmax=vmax_chi2_xx)
    ax3.set_xticks(range(len(sdcs)))
    ax3.set_xticklabels(sdcs)
    ax3.set_yticks(range(len(els)))
    ax3.set_yticklabels(els)
    ax3.set_xlabel('Source Distance Cutoff (degrees)')
    ax3.set_ylabel('Elevation Limit (degrees)')
    ax3.set_title('Reduced Chi-Squared (XX)')
    plt.colorbar(im3, ax=ax3, label='Chi2/dof')
    
    # Find best (min) chi2dof
    best_chi2_xx_flat = np.nanargmin(pivot_chi2_xx.values)
    best_chi2_xx_i, best_chi2_xx_j = np.unravel_index(best_chi2_xx_flat, pivot_chi2_xx.values.shape)
    
    # Add values to heatmap and highlight best
    for i in range(len(els)):
        for j in range(len(sdcs)):
            val = pivot_chi2_xx.iloc[i, j]
            if not np.isnan(val):
                color = 'white' if val > (vmin_chi2_xx + vmax_chi2_xx) / 2 else 'black'
                ax3.text(j, i, f'{val:.4f}', ha='center', va='center', color=color, fontsize=7)
                # Highlight best value with magenta circle
                if i == best_chi2_xx_i and j == best_chi2_xx_j:
                    from matplotlib.patches import Circle
                    circle = Circle((j, i), 0.4, linewidth=3, edgecolor='magenta', facecolor='none')
                    ax3.add_patch(circle)
    
    # Plot 4: Chi2/dof heatmap (YY)
    ax4 = fig.add_subplot(gs[1, 1])
    pivot_chi2_yy = summary_df.pivot(index='el', columns='sdc', values='mean_chi2dof_yy')
    vmin_chi2_yy = np.nanmin(pivot_chi2_yy.values)
    vmax_chi2_yy = np.nanmax(pivot_chi2_yy.values)
    im4 = ax4.imshow(pivot_chi2_yy.values, aspect='auto', cmap='RdYlGn_r', vmin=vmin_chi2_yy, vmax=vmax_chi2_yy)
    ax4.set_xticks(range(len(sdcs)))
    ax4.set_xticklabels(sdcs)
    ax4.set_yticks(range(len(els)))
    ax4.set_yticklabels(els)
    ax4.set_xlabel('Source Distance Cutoff (degrees)')
    ax4.set_ylabel('Elevation Limit (degrees)')
    ax4.set_title('Reduced Chi-Squared (YY)')
    plt.colorbar(im4, ax=ax4, label='Chi2/dof')
    
    # Find best (min) chi2dof
    best_chi2_yy_flat = np.nanargmin(pivot_chi2_yy.values)
    best_chi2_yy_i, best_chi2_yy_j = np.unravel_index(best_chi2_yy_flat, pivot_chi2_yy.values.shape)
    
    # Add values to heatmap and highlight best
    for i in range(len(els)):
        for j in range(len(sdcs)):
            val = pivot_chi2_yy.iloc[i, j]
            if not np.isnan(val):
                color = 'white' if val > (vmin_chi2_yy + vmax_chi2_yy) / 2 else 'black'
                ax4.text(j, i, f'{val:.4f}', ha='center', va='center', color=color, fontsize=7)
                # Highlight best value with magenta circle
                if i == best_chi2_yy_i and j == best_chi2_yy_j:
                    from matplotlib.patches import Circle
                    circle = Circle((j, i), 0.4, linewidth=3, edgecolor='magenta', facecolor='none')
                    ax4.add_patch(circle)
    
    # Plot 5: RMS Convergence
    ax5 = fig.add_subplot(gs[2, 0])
    
    # Find best (minimum) RMS convergence
    best_rms_idx = summary_df['rms_convergence'].idxmin()
    best_rms_sdc = summary_df.loc[best_rms_idx, 'sdc']
    best_rms_el = summary_df.loc[best_rms_idx, 'el']
    
    for el in els:
        el_data = summary_df[summary_df['el'] == el].sort_values('sdc')
        
        # Plot with stars for best value
        for idx, row in el_data.iterrows():
            marker = '*' if (row['sdc'] == best_rms_sdc and row['el'] == best_rms_el) else 'o'
            ms = 15 if marker == '*' else 6
            ax5.plot(row['sdc'], row['rms_convergence'], marker, color=f'C{els.index(el)}', 
                    markersize=ms, alpha=0.7)
        ax5.plot(el_data['sdc'], el_data['rms_convergence'], '-', label=f'el{el}', 
                color=f'C{els.index(el)}', alpha=0.7)
    
    ax5.set_xlabel('Source Distance Cutoff (degrees)')
    ax5.set_ylabel('RMS Convergence')
    ax5.set_title('RMS Convergence vs Configuration')
    ax5.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)
    ax5.grid(True, alpha=0.3)
    ax5.set_yscale('log')
    
    # Plot 6: Bad Antenna Percentage
    ax6 = fig.add_subplot(gs[2, 1])
    
    # Find best (minimum) bad antenna percentage
    best_bad_idx = summary_df['percent_bad_ants'].idxmin()
    best_bad_sdc = summary_df.loc[best_bad_idx, 'sdc']
    best_bad_el = summary_df.loc[best_bad_idx, 'el']
    
    for el in els:
        el_data = summary_df[summary_df['el'] == el].sort_values('sdc')
        
        # Plot with stars for best value
        for idx, row in el_data.iterrows():
            marker = '*' if (row['sdc'] == best_bad_sdc and row['el'] == best_bad_el) else 'o'
            ms = 15 if marker == '*' else 6
            ax6.plot(row['sdc'], row['percent_bad_ants'], marker, color=f'C{els.index(el)}', 
                    markersize=ms, alpha=0.7)
        ax6.plot(el_data['sdc'], el_data['percent_bad_ants'], '-', label=f'el{el}', 
                color=f'C{els.index(el)}', alpha=0.7)
    
    ax6.set_xlabel('Source Distance Cutoff (degrees)')
    ax6.set_ylabel('Bad Antennas (%)')
    ax6.set_title('Bad Antenna Percentage vs Configuration')
    ax6.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)
    ax6.grid(True, alpha=0.3)
    
    # Mark best configuration on line plots only
    best_sdc = int(best_config['sdc'])
    best_el = int(best_config['el'])
    for ax in [ax5, ax6]:
        ax.axvline(x=best_sdc, color='red', linestyle='--', alpha=0.3, linewidth=2)
    
    plt.suptitle(f'Calibration Quality Comparison for OBSID {obsid}', fontsize=14, fontweight='bold')
    
    # Save plot
    plot_file = datadir / f"{obsid}_cal_comparison.png"
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    print(f"\nPlots saved to: {plot_file}")
    plt.close()
    
except ImportError as e:
    print(f"\nWarning: Could not generate plots. matplotlib not available: {e}")
except Exception as e:
    print(f"\nWarning: Could not generate plots: {e}")

PYPROG
