import json
import tarfile
import sys
import os
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
from collections import defaultdict
import glob

# Set academic paper style matching the STABL Middleware 2025 paper
mpl.rcParams['font.family'] = 'serif'
mpl.rcParams['font.serif'] = ['Times New Roman', 'DejaVu Serif', 'Bitstream Vera Serif']
mpl.rcParams['pdf.fonttype'] = 42

def extract_and_parse(tar_path):
    print(f"Reading {tar_path}...")
    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith("results.json"):
                    f = tar.extractfile(member)
                    if f is not None:
                        return json.load(f)
    except Exception as e:
        print(f"Error reading {tar_path}: {e}")
        return None
    return None

def analyze_timeline(data, window_size=2.0):
    start_time = float('inf')
    end_time = 0.0
    
    # First pass: find global start and end time
    for loc in data.get("Locations", []):
        for client in loc.get("Clients", []):
            for ix in client.get("Interactions", []):
                sub_t = ix.get("SubmitTime", -1)
                if sub_t > 0:
                    start_time = min(start_time, sub_t)
                    end_time = max(end_time, sub_t)
                
                com_t = ix.get("CommitTime", -1)
                if com_t > 0:
                    end_time = max(end_time, com_t)
                    
    if start_time == float('inf'):
        return [], []

    # Shift times to start at 0
    duration = end_time - start_time
    num_windows = int(np.ceil(duration / window_size))
    
    windows = [i * window_size for i in range(num_windows)]
    committed_counts = [0] * num_windows
    
    # Second pass: bin data into windows
    for loc in data.get("Locations", []):
        for client in loc.get("Clients", []):
            for ix in client.get("Interactions", []):
                sub_t = ix.get("SubmitTime", -1)
                com_t = ix.get("CommitTime", -1)
                        
                if com_t > 0 and sub_t > 0:
                    rel_com_t = com_t - start_time
                    win_idx = int(rel_com_t / window_size)
                    if win_idx < num_windows:
                        committed_counts[win_idx] += 1
                        
    # Calculate TPS
    tps = [c / window_size for c in committed_counts]
            
    return windows, tps

def plot_stabl_paper_style(mode_files, output_dir="minion"):
    # Create figure similar to Figure 5/6 with 3 subplots sharing Y axis
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.5), sharey=True, sharex=True)
    
    # Read baseline data
    if 'none' not in mode_files:
        print("Error: Baseline (mode 'none') not found!")
        return
        
    base_data = extract_and_parse(mode_files['none'])
    base_times, base_tps = analyze_timeline(base_data, window_size=2.0)
    
    # We will plot these three modes in order
    fault_modes = ['crash-no-recovery', 'crash', 'partition']
    titles = ['Crash-no-recovery (f=3)', 'Crash (f=4, restart)', 'Partition (f=4)']
    
    line_base, line_alt, line_fail, line_rec = None, None, None, None
    
    for i, mode in enumerate(fault_modes):
        ax = axes[i]
        
        if mode not in mode_files:
            print(f"Warning: Mode {mode} not found.")
            continue
            
        alt_data = extract_and_parse(mode_files[mode])
        alt_times, alt_tps = analyze_timeline(alt_data, window_size=2.0)
        
        # 1. Plot altered (lighter blue, thinner)
        line_alt, = ax.plot(alt_times, alt_tps, color='#85C0F9', linewidth=1.5, label='altered')
        
        # 2. Plot baseline (darker blue, thicker, transparent)
        line_base, = ax.plot(base_times, base_tps, color='#0F5298', linewidth=1.5, alpha=0.9, label='baseline')
        
        # 3. Add fault injection vertical lines
        line_fail = ax.axvline(x=133, color='#D62728', linestyle='--', linewidth=1.2, label='failures')
        
        # Recovery line (Partition and Crash have recovery at t=267)
        if mode in ['crash', 'partition']:
            line_rec = ax.axvline(x=267, color='#D62728', linestyle=':', linewidth=1.2, label='recovery')
        else:
            # Add an invisible line just to keep the legend consistent
            line_rec = ax.axvline(x=267, color='#D62728', linestyle=':', linewidth=1.0, label='recovery', alpha=0)
        
        # Formatting matching the STABL paper
        ax.set_title(titles[i], fontsize=13, pad=10)
        ax.yaxis.grid(True, color='lightgray', linestyle='-')
        ax.xaxis.grid(False)
        ax.set_xlim(0, 400)
        
        # Log scale like the paper, or use linear. Since we have TPS 0-10, linear works better.
        # But we'll add 10 to ylim just to give some headroom like the paper.
        ax.set_ylim(-0.5, 10.5)
        
        # Set ticks
        ax.set_xticks([0, 100, 200, 300, 400])
        ax.tick_params(axis='both', which='major', labelsize=11)

        # Set labels
        if i == 0:
            ax.set_ylabel('Throughput (tx/s)', fontsize=13)
        if i == 1:
            ax.set_xlabel('Time (s)', fontsize=13)
            
    # Adjust layout to remove space between subplots
    plt.subplots_adjust(wspace=0)
    
    # Global Legend matching the paper exactly
    handles = [line_base, line_alt, line_fail, line_rec]
    labels = ['baseline', 'altered', 'failures', 'recovery']
    
    # Center legend above all subplots, horizontal line, no frame
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 1.12), 
               ncol=4, frameon=False, fontsize=12, handlelength=2.5)
    
    # Finalize saving
    # tight_layout with rect leaves room for the legend at the top
    plt.tight_layout(rect=[0, 0, 1, 0.9])
    plt.subplots_adjust(wspace=0) # ensure wspace is kept 0 after tight_layout
    
    output_file = os.path.join(output_dir, 'stabl_paper_throughput.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\nPlot successfully saved to {output_file}")

if __name__ == "__main__":
    modes = ['none', 'crash-no-recovery', 'crash', 'partition']
    mode_files = {}
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tarball_pattern_1 = os.path.join(script_dir, "results/**/*.results.tar.gz")
    tarball_pattern_2 = os.path.join(script_dir, "*.results.tar.gz")
    
    tarballs = glob.glob(tarball_pattern_1, recursive=True)
    tarballs.extend(glob.glob(tarball_pattern_2))
    
    for mode in modes:
        mode_tarballs = [f for f in tarballs if f"-{mode}-" in f and "quicksomke" not in f]
        if mode_tarballs:
            latest_tarball = max(mode_tarballs, key=os.path.getmtime)
            mode_files[mode] = latest_tarball
            print(f"Selected {latest_tarball} for mode '{mode}'")
            
    if not mode_files:
        print("No result tarballs found!")
        sys.exit(1)
        
    plot_stabl_paper_style(mode_files, output_dir=script_dir)
