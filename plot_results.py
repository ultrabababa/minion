#!/usr/bin/env python3
import glob
import json
import re
import tarfile
import sys
import os
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

BASELINE_COLOR = '#0F5298'  # dark blue
ALTERED_COLOR = '#85C0F9'   # light blue

# Set academic paper style matching the STABL Middleware 2025 paper
mpl.rcParams['font.family'] = 'serif'
mpl.rcParams['font.serif'] = ['Times New Roman', 'DejaVu Serif', 'Bitstream Vera Serif']
mpl.rcParams['pdf.fonttype'] = 42

DEFAULT_WARMUP_SKIP = 0.0
DEFAULT_WINDOW_SIZE = 5.0
DEFAULT_WINDOW_STEP = 1.0


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


def infer_duration(data):
    """Infer experiment duration from submit time span, rounded to nearest 100s."""
    if data is None:
        return 0
    min_t = float('inf')
    max_t = 0.0
    for loc in data.get("Locations", []):
        for client in loc.get("Clients", []):
            for ix in client.get("Interactions", []):
                sub_t = ix.get("SubmitTime", -1)
                if sub_t > 0:
                    min_t = min(min_t, sub_t)
                    max_t = max(max_t, sub_t)
    if min_t == float('inf'):
        return 0
    raw = max_t - min_t
    # Round to nearest 100s (e.g. 799.8 → 800, 401.2 → 400)
    return int(round(raw / 100.0)) * 100


def analyze_timeline(
    data,
    window_size=DEFAULT_WINDOW_SIZE,
    step_size=DEFAULT_WINDOW_STEP,
    warmup_skip=DEFAULT_WARMUP_SKIP,
):
    """
    Compute throughput time series with a sliding window.
    - window_size: width of counting window in seconds.
    - step_size: step between adjacent points in seconds.
    - warmup_skip: skip this many seconds from first SubmitTime.
    Returns (times, tps), where each point is throughput in (t-window, t].
    """
    if data is None:
        return [], []

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

    # Skip warmup burst; plot_t=0 corresponds to absolute time (start_time + warmup_skip)
    plot_origin = start_time + warmup_skip

    max_submit_time = 0.0
    commit_times = []

    for loc in data.get("Locations", []):
        for client in loc.get("Clients", []):
            for ix in client.get("Interactions", []):
                sub_t = ix.get("SubmitTime", -1)
                if sub_t > 0:
                    max_submit_time = max(max_submit_time, sub_t)
                com_t = ix.get("CommitTime", -1)
                if com_t > 0:
                    commit_times.append(com_t)

    # Horizon uses submit span so post-fault zero-throughput periods remain visible.
    horizon = max_submit_time
    duration = horizon - plot_origin
    if duration <= 0 or window_size <= 0 or step_size <= 0:
        return [], []

    commit_times.sort()
    if duration < window_size:
        return [], []

    # Sliding windows: t from window_size to duration, step=step_size.
    sample_times = np.arange(window_size, duration + 1e-9, step_size)
    if sample_times.size == 0:
        return [], []

    commit_arr = np.array(commit_times, dtype=float)
    starts = plot_origin + sample_times - window_size
    ends = plot_origin + sample_times

    left_idx = np.searchsorted(commit_arr, starts, side="right")
    right_idx = np.searchsorted(commit_arr, ends, side="right")
    counts = right_idx - left_idx
    tps = (counts / window_size).tolist()

    return sample_times.tolist(), tps


def analyze_commit_progress(data, step_size=DEFAULT_WINDOW_STEP, warmup_skip=DEFAULT_WARMUP_SKIP):
    """Compute cumulative commit progress (% committed / submitted) over time."""
    if data is None or step_size <= 0:
        return [], []

    start_time = float('inf')
    max_submit_time = 0.0
    submit_times = []
    commit_times = []

    for loc in data.get("Locations", []):
        for client in loc.get("Clients", []):
            for ix in client.get("Interactions", []):
                sub_t = ix.get("SubmitTime", -1)
                if sub_t > 0:
                    start_time = min(start_time, sub_t)
                    max_submit_time = max(max_submit_time, sub_t)
                    submit_times.append(sub_t)
                com_t = ix.get("CommitTime", -1)
                if com_t > 0:
                    commit_times.append(com_t)

    if start_time == float('inf'):
        return [], []

    origin = start_time + warmup_skip
    duration = max_submit_time - origin
    if duration <= 0:
        return [], []

    t = np.arange(0.0, duration + 1e-9, step_size)
    if t.size == 0:
        return [], []

    com_arr = np.array(sorted(commit_times), dtype=float)
    abs_t = origin + t

    committed = np.searchsorted(com_arr, abs_t, side='right')
    
    # Use raw cumulative count instead of a potentially deceptive percentage
    # (since the number of submitted requests also flatlines when the system stalls)
    progress_count = committed.astype(float)

    return t.tolist(), progress_count.tolist()


def _make_xticks(duration, warmup_skip=DEFAULT_WARMUP_SKIP):
    """Generate nice x-axis ticks for a given experiment duration.
    Returns (tick_positions, tick_labels) in plot coordinates (after warmup shift)."""
    if duration <= 100:
        step = 20
    elif duration <= 500:
        step = 100
    else:
        step = 200
    raw_ticks = list(range(0, duration + 1, step))
    positions = [t - warmup_skip for t in raw_ticks if t >= warmup_skip]
    labels = [str(int(t + warmup_skip)) for t in positions]
    return positions, labels


def _format_axes(ax, duration, warmup_skip=DEFAULT_WARMUP_SKIP, log_y=True):
    """Apply consistent axis formatting for a given experiment duration."""
    ax.yaxis.grid(True, color='lightgray', linestyle='-')
    ax.xaxis.grid(False)

    xmax = duration - warmup_skip
    ax.set_xlim(0, xmax)
    if log_y:
        ax.set_yscale('log')
        ax.set_ylim(1, 1000)
        ax.set_yticks([1, 10, 100, 1000])
    else:
        ax.set_ylim(-5, 250)
        ax.set_yticks([0, 50, 100, 150, 200])

    positions, labels = _make_xticks(duration, warmup_skip)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    ax.tick_params(axis='both', which='major', labelsize=11)
    ax.set_ylabel('Throughput (tx/s)', fontsize=12)
    ax.set_xlabel('Time (s)', fontsize=12)


def plot_single_mode(ax, base_times, base_tps, alt_times, alt_tps,
                     title, has_recovery, duration,
                     warmup_skip=DEFAULT_WARMUP_SKIP, log_y=True):
    """Plot one fault mode panel onto a given Axes object. Returns legend handles.
    duration: experiment duration in seconds (e.g. 400, 800).
    Fault/recovery lines follow the STABL formula: fault at duration/6, recovery at duration/3."""
    # baseline: dark blue
    line_base, = ax.plot(base_times, base_tps, color=BASELINE_COLOR, linewidth=0.9,
                         alpha=0.9, label='baseline', zorder=2)
    # altered: orange
    line_alt, = ax.plot(alt_times, alt_tps, color=ALTERED_COLOR, linewidth=0.9,
                        alpha=0.95, label='altered', zorder=3)

    # Fault/recovery times from STABL formula
    fault_at = duration / 6.0
    recovery_at = duration / 3.0
    fail_x = fault_at - warmup_skip
    recovery_x = recovery_at - warmup_skip

    line_fail = ax.axvline(x=fail_x, color='#D62728', linestyle='--', linewidth=1.2,
                           label=f'failures (t={int(fault_at)}s)')

    if has_recovery:
        line_rec = ax.axvline(x=recovery_x, color='#D62728', linestyle=':', linewidth=1.2,
                              label=f'recovery (t={int(recovery_at)}s)')
    else:
        line_rec = ax.axvline(x=recovery_x, color='#D62728', linestyle=':', linewidth=1.0,
                              label='recovery', alpha=0)

    ax.set_title(title, fontsize=13, pad=8)
    _format_axes(ax, duration, warmup_skip, log_y=log_y)

    return line_base, line_alt, line_fail, line_rec


def plot_stabl_paper_style(
    mode_files,
    output_dir="minion",
    window_size=DEFAULT_WINDOW_SIZE,
    step_size=DEFAULT_WINDOW_STEP,
    warmup_skip=DEFAULT_WARMUP_SKIP,
    log_y=True,
    n_nodes=None,
):
    """Generate per-mode and combined throughput plots.
    mode_files: dict of mode -> (path, failures)
    """
    if 'none' not in mode_files:
        print("Error: Baseline (mode 'none') not found!")
        return

    base_path, _ = mode_files['none']
    base_data = extract_and_parse(base_path)
    if base_data is None:
        print("Error: Could not parse baseline data!")
        return
    duration = infer_duration(base_data)
    if duration == 0:
        print("Error: Could not infer experiment duration from baseline data!")
        return
    print(f"Inferred experiment duration: {duration}s")

    base_times, base_tps = analyze_timeline(
        base_data,
        window_size=window_size,
        step_size=step_size,
        warmup_skip=warmup_skip,
    )

    fault_modes  = ['crash-no-recovery', 'crash', 'partition']
    mode_labels  = {'crash-no-recovery': 'Crash (no recovery)',
                    'crash':             'Crash (with recovery)',
                    'partition':         'Partition (with recovery)'}
    filenames    = ['plot_crash_no_recovery.png', 'plot_crash.png', 'plot_partition.png']
    has_rec      = {'crash-no-recovery': False, 'crash': True, 'partition': True}

    # Compute BFT fault tolerance bound: f_max = floor((N-1)/3)
    f_max = (n_nodes - 1) // 3 if n_nodes else None

    # Build global info banner text
    banner = f"asonnino-hotstuff  \u2022  N={n_nodes}  \u2022  f_max={f_max}  \u2022  100 TPS target" if n_nodes else None

    def _add_banner(fig):
        if banner:
            fig.text(0.5, 0.97, banner, ha='center', va='top', fontsize=9,
                     color='#666666', style='italic', transform=fig.transFigure)

    def _make_f_tag(failures):
        """Return f label: 'f=7=f_max' or 'f=8 > f_max'."""
        if f_max is None:
            return f"f={failures}"
        if failures == f_max:
            return f"f={failures}=f_max"
        elif failures < f_max:
            return f"f={failures} (f_max={f_max})"
        else:
            return f"f={failures} > f_max"

    # --- Standalone baseline figure ---
    fig, ax = plt.subplots(figsize=(8, 4))
    line_base, = ax.plot(base_times, base_tps, color=BASELINE_COLOR, linewidth=0.9,
                         alpha=0.9, label='baseline', zorder=2)
    ax.set_title('Baseline (no fault, f=0)', fontsize=13, pad=8)
    _add_banner(fig)
    _format_axes(ax, duration, warmup_skip=warmup_skip, log_y=log_y)
    fig.legend([line_base], ['baseline'], loc='upper center',
               bbox_to_anchor=(0.5, 1.05), ncol=1,
               frameon=False, fontsize=11, handlelength=2.2)
    plt.tight_layout(rect=(0, 0, 1, 0.90))
    base_out = os.path.join(output_dir, 'plot_baseline.png')
    plt.savefig(base_out, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {base_out}")

    # --- Per-mode fault figures ---
    saved = []
    for mode, fname in zip(fault_modes, filenames):
        if mode not in mode_files:
            print(f"Warning: Mode {mode} not found, skipping.")
            continue

        alt_path, failures = mode_files[mode]
        alt_data = extract_and_parse(alt_path)
        if alt_data is None:
            print(f"Warning: Could not parse data for mode {mode}, skipping.")
            continue
        alt_times, alt_tps = analyze_timeline(
            alt_data,
            window_size=window_size,
            step_size=step_size,
            warmup_skip=warmup_skip,
        )

        f_tag = _make_f_tag(failures)
        title = f"{mode_labels[mode]}  ({f_tag})"
        rec = has_rec[mode]

        fig, ax = plt.subplots(figsize=(8, 4))
        handles = plot_single_mode(
            ax,
            base_times,
            base_tps,
            alt_times,
            alt_tps,
            title,
            rec,
            duration,
            warmup_skip=warmup_skip,
            log_y=log_y,
        )

        legend_labels = ['baseline', 'altered', 'failures', 'recovery']
        fig.legend(handles, legend_labels, loc='upper center',
                   bbox_to_anchor=(0.5, 1.05), ncol=4,
                   frameon=False, fontsize=11, handlelength=2.2)

        _add_banner(fig)
        plt.tight_layout(rect=(0, 0, 1, 0.90))
        out = os.path.join(output_dir, fname)
        plt.savefig(out, dpi=300, bbox_inches='tight')
        plt.close(fig)
        saved.append(out)
        print(f"Saved {out}")

    # --- Combined 3-panel figure ---
    fig, axes = plt.subplots(1, 3, figsize=(16, 4), sharey=True, sharex=True)
    last_handles = None
    for i, mode in enumerate(fault_modes):
        if mode not in mode_files:
            continue
        alt_path, failures = mode_files[mode]
        alt_data = extract_and_parse(alt_path)
        if alt_data is None:
            continue
        alt_times, alt_tps = analyze_timeline(
            alt_data,
            window_size=window_size,
            step_size=step_size,
            warmup_skip=warmup_skip,
        )
        f_tag = _make_f_tag(failures)
        title = f"{mode_labels[mode]}  ({f_tag})"
        last_handles = plot_single_mode(
            axes[i],
            base_times,
            base_tps,
            alt_times,
            alt_tps,
            title,
            has_rec[mode],
            duration,
            warmup_skip=warmup_skip,
            log_y=log_y,
        )

    legend_labels = ['baseline', 'altered', 'failures', 'recovery']
    fig.legend(last_handles, legend_labels, loc='upper center',
               bbox_to_anchor=(0.5, 1.12), ncol=4,
               frameon=False, fontsize=11, handlelength=2.2)
    _add_banner(fig)
    plt.tight_layout(rect=(0, 0, 1, 0.85))
    combined_out = os.path.join(output_dir, 'stabl_paper_throughput.png')
    plt.savefig(combined_out, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved combined overview to {combined_out}")

    # --- Combined 3-panel commit-progress figure ---
    fig, axes = plt.subplots(1, 3, figsize=(16, 4), sharey=True, sharex=True)
    base_prog_t, base_prog = analyze_commit_progress(
        base_data,
        step_size=step_size,
        warmup_skip=warmup_skip,
    )

    prog_handles = None
    for i, mode in enumerate(fault_modes):
        ax = axes[i]
        if mode not in mode_files:
            continue
        alt_path, failures = mode_files[mode]
        alt_data = extract_and_parse(alt_path)
        if alt_data is None:
            continue
        alt_prog_t, alt_prog = analyze_commit_progress(
            alt_data,
            step_size=step_size,
            warmup_skip=warmup_skip,
        )

        line_base_p, = ax.plot(base_prog_t, base_prog, color=BASELINE_COLOR, linewidth=1.0, alpha=0.9, label='baseline')
        line_alt_p, = ax.plot(alt_prog_t, alt_prog, color=ALTERED_COLOR, linewidth=1.0, alpha=0.95, label='altered')

        fault_at = duration / 6.0
        recovery_at = duration / 3.0
        line_fail_p = ax.axvline(x=(fault_at - warmup_skip), color='#D62728', linestyle='--', linewidth=1.2)
        if has_rec[mode]:
            line_rec_p = ax.axvline(x=(recovery_at - warmup_skip), color='#D62728', linestyle=':', linewidth=1.2)
        else:
            line_rec_p = ax.axvline(x=(recovery_at - warmup_skip), color='#D62728', linestyle=':', linewidth=1.0, alpha=0)

        prog_handles = (line_base_p, line_alt_p, line_fail_p, line_rec_p)

        f_tag = _make_f_tag(failures)
        ax.set_title(f"{mode_labels[mode]}  ({f_tag})", fontsize=13, pad=8)
        ax.yaxis.grid(True, color='lightgray', linestyle='-')
        ax.xaxis.grid(False)
        ax.set_xlim(0, duration - warmup_skip)
        ax.set_ylim(bottom=0)
        positions, labels = _make_xticks(duration, warmup_skip)
        ax.set_xticks(positions)
        ax.set_xticklabels(labels)
        ax.tick_params(axis='both', which='major', labelsize=11)
        if i == 0:
            ax.set_ylabel('Cumulative Commits', fontsize=12)
        else:
            ax.set_ylabel('')
        ax.set_xlabel('Time (s)', fontsize=12)

    if prog_handles:
        fig.legend(prog_handles, ['baseline', 'altered', 'failures', 'recovery'],
                   loc='upper center', bbox_to_anchor=(0.5, 1.12),
                   ncol=4, frameon=False, fontsize=12, handlelength=2.5)

    _add_banner(fig)
    plt.tight_layout(rect=(0, 0, 1, 0.86))
    plt.subplots_adjust(wspace=0.06)
    progress_out = os.path.join(output_dir, 'stabl_commit_progress.png')
    plt.savefig(progress_out, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved commit-progress overview to {progress_out}")


def plot_byzantine_comparison(
    base_files,
    redundant_files,
    output_dir=".",
    window_size=DEFAULT_WINDOW_SIZE,
    step_size=DEFAULT_WINDOW_STEP,
    warmup_skip=DEFAULT_WARMUP_SKIP,
    log_y=True,
    n_nodes=None,
):
    """
    Plot Byzantine Node Tolerance comparison: standard client vs secure client (redundancy=4).
    Both run with no fault injection (mode='none'). The overhead of requiring all 4 replicas
    to respond (tB+1 threshold) shows up as reduced/stable throughput with higher latency.
    base_files / redundant_files: dict of mode -> (path, failures)
    """
    if 'none' not in base_files:
        print("Byzantine plot: baseline (hotstuff, none) not found, skipping.")
        return
    if 'none' not in redundant_files:
        print("Byzantine plot: redundant baseline (hotstuff-redundant, none) not found, skipping.")
        return

    base_path, _ = base_files['none']
    red_path,  _ = redundant_files['none']
    base_data = extract_and_parse(base_path)
    red_data  = extract_and_parse(red_path)
    if base_data is None or red_data is None:
        print("Byzantine plot: could not parse data, skipping.")
        return

    # Use the longer duration of the two datasets for axis formatting
    dur_base = infer_duration(base_data)
    dur_red  = infer_duration(red_data)
    duration = max(dur_base, dur_red)
    if duration == 0:
        print("Byzantine plot: could not infer duration, skipping.")
        return
    print(f"Byzantine plot: inferred duration = {duration}s")

    base_times, base_tps = analyze_timeline(
        base_data,
        window_size=window_size,
        step_size=step_size,
        warmup_skip=warmup_skip,
    )
    red_times, red_tps = analyze_timeline(
        red_data,
        window_size=window_size,
        step_size=step_size,
        warmup_skip=warmup_skip,
    )

    # Extract redundancy value from the last numeric field before the timestamp
    red_basename = os.path.basename(red_path)
    red_m = re.search(r'-(\d+)_\d{4}-\d{2}-\d{2}', red_basename)
    redundancy = int(red_m.group(1)) if red_m else 4

    fig, ax = plt.subplots(figsize=(8, 4))

    line_base, = ax.plot(base_times, base_tps, color=BASELINE_COLOR, linewidth=0.9,
                         alpha=0.9, label='standard client (f=0)', zorder=2)
    line_red,  = ax.plot(red_times,  red_tps,  color=ALTERED_COLOR, linewidth=0.9,
                         alpha=0.85, label=f'secure client (redundancy={redundancy})', zorder=3)

    f_max = (n_nodes - 1) // 3 if n_nodes else None
    banner = f"asonnino-hotstuff  \u2022  N={n_nodes}  \u2022  f_max={f_max}  \u2022  100 TPS target" if n_nodes else None
    if banner:
        fig.text(0.5, 0.97, banner, ha='center', va='top', fontsize=9,
                 color='#666666', style='italic', transform=fig.transFigure)
    ax.set_title('Byzantine Node Tolerance \u2014 Secure Client Overhead', fontsize=13, pad=8)
    _format_axes(ax, duration, warmup_skip=warmup_skip, log_y=log_y)

    fig.legend([line_base, line_red],
               ['standard client (f=0)', f'secure client (redundancy={redundancy})'],
               loc='upper center', bbox_to_anchor=(0.5, 1.05),
               ncol=2, frameon=False, fontsize=11, handlelength=2.2)

    plt.tight_layout(rect=(0, 0, 1, 0.90))
    out = os.path.join(output_dir, 'plot_byzantine.png')
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out}")


# Tarball filename format:
#   {blockchain}-{sec}-{cli}-{nodes}-{mode}-{failures}-{redundancy}_{timestamp}.results.tar.gz
# Examples:
#   hotstuff-1-5-10-none-0-1_2026-03-11-16-27-13.results.tar.gz
#   hotstuff-1-5-10-crash-no-recovery-1-1_2026-03-11-07-50-00.results.tar.gz
#   hotstuff-redundant-1-5-10-none-0-4_2026-03-09-18-33-37.results.tar.gz
#   asonnino-hotstuff-1-5-10-none-0-1_2026-03-22-17-23-05.results.tar.gz
#   asonnino-hotstuff-redundant-1-5-10-none-0-4_2026-03-22-19-00-00.results.tar.gz
TARBALL_RE = re.compile(
    r'^((?:asonnino-)?hotstuff(?:-redundant)?)'  # blockchain key
    r'-\d+-\d+-(\d+)-'                # secondaries-clients-nodes
    r'(none|crash-no-recovery|crash|partition)'  # mode (longest match first)
    r'-(\d+)-(\d+)_'                # failures-redundancy
    r'.+\.results\.tar\.gz$'
)


def parse_tarball_name(path):
    """Extract (blockchain, nodes, mode, failures, redundancy) from tarball filename."""
    basename = os.path.basename(path)
    m = TARBALL_RE.match(basename)
    if m:
        return m.group(1), int(m.group(2)), m.group(3), int(m.group(4)), int(m.group(5))
    return None


def select_latest_matching(records, blockchain, mode, failures, redundancy=None):
    """Pick latest tarball matching the exact scenario constraints."""
    matches = [r for r in records if r['blockchain'] == blockchain and r['mode'] == mode and r['failures'] == failures]
    if redundancy is not None:
        matches = [r for r in matches if r['redundancy'] == redundancy]
    if not matches:
        return None
    return max(matches, key=lambda r: os.path.getmtime(r['path']))


def build_final_suite_records(records):
    """Select required records for --final-suite from either hotstuff or asonnino-hotstuff family.
    Automatically detects the f values used in the directory instead of hardcoding N=10 values."""
    candidates = [
        ('hotstuff', 'hotstuff-redundant'),
        ('asonnino-hotstuff', 'asonnino-hotstuff-redundant'),
    ]

    best_family = None
    best_selected = None
    best_missing = None

    for base_bc, redundant_bc in candidates:
        # Auto-detect f values from available tarballs for this family
        crash_f = None
        partition_f = None
        for r in records:
            if r['blockchain'] == base_bc:
                if r['mode'] == 'crash':
                    if crash_f is None or r['failures'] > crash_f:
                        crash_f = r['failures']
                elif r['mode'] == 'partition':
                    if partition_f is None or r['failures'] > partition_f:
                        partition_f = r['failures']
                elif r['mode'] == 'crash-no-recovery':
                    if crash_f is None or r['failures'] > crash_f:
                        crash_f = r['failures']

        # crash-no-recovery uses f-1 (BFT bound), crash and partition use f
        cnr_f = crash_f - 1 if crash_f else None
        crash_f_val = crash_f
        partition_f_val = partition_f

        required_modes = [
            ('none', 0, 1),
        ]
        if cnr_f is not None:
            required_modes.append(('crash-no-recovery', cnr_f, 1))
        if crash_f_val is not None:
            required_modes.append(('crash', crash_f_val, 1))
        if partition_f_val is not None:
            required_modes.append(('partition', partition_f_val, 1))

        selected = {}
        missing = []

        for mode, failures, redundancy in required_modes:
            rec = select_latest_matching(records, base_bc, mode, failures, redundancy=redundancy)
            if rec is None:
                missing.append((base_bc, mode, failures, redundancy))
            else:
                selected[(base_bc, mode)] = rec

        rec = select_latest_matching(records, redundant_bc, 'none', 0, redundancy=4)
        if rec is None:
            missing.append((redundant_bc, 'none', 0, 4))
        else:
            selected[(redundant_bc, 'none')] = rec

        if best_missing is None or len(missing) < len(best_missing):
            best_family = (base_bc, redundant_bc, crash_f_val, partition_f_val)
            best_selected = selected
            best_missing = missing

        if not missing:
            return best_family, best_selected, best_missing

    return best_family, best_selected, best_missing


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Plot throughput comparison charts from Diablo benchmark results.",
        epilog="Examples:\n"
                "  python plot_results.py                     # scan current dir\n"
                "  python plot_results.py -d results/re0309   # scan specific dir\n"
               "  python plot_results.py -d .                # explicit current dir\n"
               "  python plot_results.py -d . --final-suite  # require final experiment set\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-d", "--dir", default=".",
                        help="Directory containing .results.tar.gz files (default: current dir, non-recursive)")
    parser.add_argument("--window", type=float, default=DEFAULT_WINDOW_SIZE,
                        help="Sliding window size in seconds (default: 5)")
    parser.add_argument("--step", type=float, default=DEFAULT_WINDOW_STEP,
                        help="Sliding step in seconds (default: 1)")
    parser.add_argument("--warmup-skip", type=float, default=DEFAULT_WARMUP_SKIP,
                        help="Skip this many seconds from first submit timestamp (default: 0)")
    parser.add_argument("--linear-y", action="store_true",
                        help="Use linear Y axis (default is log-scale Y)")
    parser.add_argument("--final-suite", action="store_true",
                        help="Require/select final test suite for one family (hotstuff* or asonnino-hotstuff*): none f0, crash-no-recovery f3, crash f4, partition f4, and *-redundant none f0 r4")
    args = parser.parse_args()

    search_dir = os.path.abspath(args.dir)
    if not os.path.isdir(search_dir):
        print(f"Error: {search_dir} is not a directory")
        sys.exit(1)

    # Scan directory (non-recursive) for tarball files
    tarballs = sorted(glob.glob(os.path.join(search_dir, "*.results.tar.gz")))
    if not tarballs:
        print(f"No .results.tar.gz files found in {search_dir}")
        sys.exit(1)

    mode_files = {}             # hotstuff: mode -> (path, failures) (latest by mtime)
    redundant_mode_files = {}   # hotstuff-redundant: mode -> (path, failures)
    parsed_records = []

    for path in tarballs:
        parsed = parse_tarball_name(path)
        if parsed is None:
            continue
        blockchain, n_nodes, mode, failures, redundancy = parsed
        parsed_records.append({
            'path': path,
            'blockchain': blockchain,
            'n_nodes': n_nodes,
            'mode': mode,
            'failures': failures,
            'redundancy': redundancy,
        })
        target = redundant_mode_files if blockchain.endswith('-redundant') else mode_files
        # Keep the latest file for each mode
        if mode not in target or os.path.getmtime(path) > os.path.getmtime(target[mode][0]):
            target[mode] = (path, failures)

    if args.final_suite:
        family, selected, missing = build_final_suite_records(parsed_records)

        if missing:
            print("Missing required final-suite tarballs:")
            for bc, mode, failures, redundancy in missing:
                print(f"  - {bc} mode={mode} f={failures} r={redundancy}")
            sys.exit(2)

        if family is None or selected is None:
            print("Error: could not determine final-suite blockchain family")
            sys.exit(2)

        base_bc, redundant_bc, crash_f, partition_f = family

        # Auto-detect N from any record
        n_nodes = None
        for r in parsed_records:
            if r.get('n_nodes'):
                n_nodes = r['n_nodes']
                break

        mode_files = {
            'none': (selected[(base_bc, 'none')]['path'], 0),
        }
        if (base_bc, 'crash-no-recovery') in selected:
            mode_files['crash-no-recovery'] = (selected[(base_bc, 'crash-no-recovery')]['path'], crash_f - 1 if crash_f else 0)
        if (base_bc, 'crash') in selected:
            mode_files['crash'] = (selected[(base_bc, 'crash')]['path'], crash_f or 0)
        if (base_bc, 'partition') in selected:
            mode_files['partition'] = (selected[(base_bc, 'partition')]['path'], partition_f or 0)
        redundant_mode_files = {
            'none': (selected[(redundant_bc, 'none')]['path'], 0),
        }

    # Print selection
    for mode, (path, failures) in sorted(mode_files.items()):
        print(f"[hotstuff]           mode '{mode}' f={failures}: {os.path.basename(path)}")
    for mode, (path, failures) in sorted(redundant_mode_files.items()):
        print(f"[hotstuff-redundant] mode '{mode}' f={failures}: {os.path.basename(path)}")

    if not mode_files and not redundant_mode_files:
        print("No valid result tarballs found!")
        sys.exit(1)

    log_y = not args.linear_y

    if mode_files:
        plot_stabl_paper_style(
            mode_files,
            output_dir=search_dir,
            window_size=args.window,
            step_size=args.step,
            warmup_skip=args.warmup_skip,
            log_y=log_y,
            n_nodes=n_nodes,
        )
    if redundant_mode_files and 'none' in mode_files:
        plot_byzantine_comparison(
            mode_files,
            redundant_mode_files,
            output_dir=search_dir,
            window_size=args.window,
            step_size=args.step,
            warmup_skip=args.warmup_skip,
            log_y=log_y,
            n_nodes=n_nodes,
        )
