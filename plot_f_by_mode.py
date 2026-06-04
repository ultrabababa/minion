#!/usr/bin/env python3
import argparse
import glob
import json
import os
import re
import tarfile

import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

BASELINE_COLOR = '#0F5298'
ALTERED_COLOR = '#E76F51'

mpl.rcParams['font.family'] = 'serif'
mpl.rcParams['font.serif'] = ['Times New Roman', 'DejaVu Serif', 'Bitstream Vera Serif']
mpl.rcParams['pdf.fonttype'] = 42

TARBALL_RE = re.compile(
    r'^((?:asonnino-)?hotstuff(?:-redundant)?)'
    r'-\d+-\d+-(\d+)-'
    r'(none|crash-no-recovery|crash|partition)'
    r'-(\d+)-(\d+)_'
    r'.+\.results\.tar\.gz$'
)


def parse_tarball_name(path):
    basename = os.path.basename(path)
    m = TARBALL_RE.match(basename)
    if m:
        return m.group(1), int(m.group(2)), m.group(3), int(m.group(4)), int(m.group(5))
    return None


def select_latest_matching(records, blockchain, mode, failures, redundancy=1):
    matches = [r for r in records if r['blockchain'] == blockchain and r['mode'] == mode and r['failures'] == failures and r['redundancy'] == redundancy]
    if not matches:
        return None
    return max(matches, key=lambda r: os.path.getmtime(r['path']))


def extract_and_parse(tar_path):
    with tarfile.open(tar_path, 'r:gz') as tar:
        for member in tar.getmembers():
            if member.name.endswith('results.json'):
                f = tar.extractfile(member)
                if f is not None:
                    return json.load(f)
    return None


def infer_duration(data):
    min_t = float('inf')
    max_t = 0.0
    for loc in data.get('Locations', []):
        for client in loc.get('Clients', []):
            for ix in client.get('Interactions', []):
                sub_t = ix.get('SubmitTime', -1)
                if sub_t > 0:
                    min_t = min(min_t, sub_t)
                    max_t = max(max_t, sub_t)
    if min_t == float('inf'):
        return 0
    return int(round((max_t - min_t) / 100.0)) * 100


def analyze_timeline(data, window_size=5.0, step_size=1.0, warmup_skip=0.0):
    if data is None:
        return [], []

    start_time = float('inf')
    max_submit_time = 0.0
    commit_times = []

    for loc in data.get('Locations', []):
        for client in loc.get('Clients', []):
            for ix in client.get('Interactions', []):
                sub_t = ix.get('SubmitTime', -1)
                if sub_t > 0:
                    start_time = min(start_time, sub_t)
                    max_submit_time = max(max_submit_time, sub_t)
                com_t = ix.get('CommitTime', -1)
                if com_t > 0:
                    commit_times.append(com_t)

    if start_time == float('inf'):
        return [], []

    plot_origin = start_time + warmup_skip
    duration = max_submit_time - plot_origin
    if duration <= 0 or window_size <= 0 or step_size <= 0 or duration < window_size:
        return [], []

    sample_times = np.arange(window_size, duration + 1e-9, step_size)
    if sample_times.size == 0:
        return [], []

    commit_arr = np.array(sorted(commit_times), dtype=float)
    starts = plot_origin + sample_times - window_size
    ends = plot_origin + sample_times
    left_idx = np.searchsorted(commit_arr, starts, side='right')
    right_idx = np.searchsorted(commit_arr, ends, side='right')
    counts = right_idx - left_idx
    tps = (counts / window_size).tolist()
    return sample_times.tolist(), tps


def analyze_commit_progress(data, step_size=1.0, warmup_skip=0.0):
    if data is None:
        return [], []

    start_time = float('inf')
    max_submit_time = 0.0
    commit_times = []

    for loc in data.get('Locations', []):
        for client in loc.get('Clients', []):
            for ix in client.get('Interactions', []):
                sub_t = ix.get('SubmitTime', -1)
                if sub_t > 0:
                    start_time = min(start_time, sub_t)
                    max_submit_time = max(max_submit_time, sub_t)
                com_t = ix.get('CommitTime', -1)
                if com_t > 0:
                    commit_times.append(com_t)

    if start_time == float('inf'):
        return [], []

    plot_origin = start_time + warmup_skip
    duration = max_submit_time - plot_origin
    if duration <= 0 or step_size <= 0:
        return [], []

    sample_times = np.arange(0.0, duration + 1e-9, step_size)
    commit_arr = np.array(sorted(commit_times), dtype=float)
    ends = plot_origin + sample_times
    counts = np.searchsorted(commit_arr, ends, side='right')
    return sample_times.tolist(), counts.tolist()


def _make_xticks(duration, warmup_skip=0.0):
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


def _format_axes(ax, duration, warmup_skip=0.0, log_y=True):
    ax.yaxis.grid(True, color='lightgray', linestyle='-')
    ax.xaxis.grid(False)
    ax.set_xlim(0, duration - warmup_skip)
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
    ax.set_ylabel('Throughput (tx/s)', fontsize=12)
    ax.set_xlabel('Time (s)', fontsize=12)


def add_fault_recovery_lines(ax, duration, warmup_skip=0.0, has_recovery=True):
    fault_at = duration / 6.0
    recovery_at = duration / 3.0
    line_fail = ax.axvline(x=(fault_at - warmup_skip), color='#D62728', linestyle='--', linewidth=1.2)
    if has_recovery:
        line_rec = ax.axvline(x=(recovery_at - warmup_skip), color='#D62728', linestyle=':', linewidth=1.2)
    else:
        line_rec = ax.axvline(x=(recovery_at - warmup_skip), color='#D62728', linestyle=':', linewidth=1.0, alpha=0)
    return line_fail, line_rec


def choose_family(records, requested):
    if requested:
        return requested
    families = ['asonnino-hotstuff', 'hotstuff']
    for fam in families:
        if any(r['blockchain'] == fam for r in records):
            return fam
    return 'asonnino-hotstuff'


def _make_setup_subtitle(mode, f, redundancy, n_nodes):
    mode_labels = {
        'none': 'No fault injection',
        'crash-no-recovery': 'Crash (no recovery)',
        'crash': 'Crash (with recovery)',
        'partition': 'Network partition (with recovery)',
    }
    mode_text = mode_labels.get(mode, mode)
    parts = [f'N={n_nodes}', mode_text]
    if f > 0:
        parts.append(f'f={f}')
    if redundancy > 1:
        parts.append(f'redundancy={redundancy}')
    return ', '.join(parts)


def plot_byzantine_mode(search_dir, records, family, window_size, step_size, warmup_skip, log_y):
    all_records = list(records)
    parent_dir = os.path.dirname(search_dir)
    parent_tarballs = sorted(glob.glob(os.path.join(parent_dir, '*.results.tar.gz')))
    for path in parent_tarballs:
        parsed = parse_tarball_name(path)
        if parsed is None:
            continue
        bc, n_nodes, mode, f, r = parsed
        all_records.append({'path': path, 'blockchain': bc, 'n_nodes': n_nodes, 'mode': mode, 'failures': f, 'redundancy': r})

    base = select_latest_matching(all_records, family, 'none', 0, 1)
    if base is None:
        raise RuntimeError(f'missing baseline none f=0 r=1 for family {family}')

    red_bc = f'{family}-redundant'
    secure = select_latest_matching(all_records, red_bc, 'none', 0, 4)
    if secure is None:
        raise RuntimeError(f'missing secure-client tarball {red_bc} none f=0 r=4')

    base_data = extract_and_parse(base['path'])
    sec_data = extract_and_parse(secure['path'])
    duration = infer_duration(base_data)

    n_nodes = all_records[0]['n_nodes'] if all_records else '?'

    base_times, base_tps = analyze_timeline(base_data, window_size, step_size, warmup_skip)
    sec_times, sec_tps = analyze_timeline(sec_data, window_size, step_size, warmup_skip)

    fig, ax = plt.subplots(figsize=(8, 4))
    l1, = ax.plot(base_times, base_tps, color=BASELINE_COLOR, linewidth=0.9, alpha=0.9, label='standard client (f=0)')
    l2, = ax.plot(sec_times, sec_tps, color=ALTERED_COLOR, linewidth=0.9, alpha=0.95, label='secure client (redundancy=4)')
    ax.set_title(_make_setup_subtitle('none', 0, 4, n_nodes), fontsize=11, pad=8)
    _format_axes(ax, duration, warmup_skip, log_y)
    fig.legend([l1, l2], ['standard client (f=0)', 'secure client (redundancy=4)'], loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=2, frameon=False, fontsize=11)
    plt.tight_layout(rect=(0, 0, 1, 0.90))
    out = os.path.join(search_dir, 'plot_byzantine.png')
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved {out}')

    base_prog_t, base_prog = analyze_commit_progress(base_data, step_size=step_size, warmup_skip=warmup_skip)
    sec_prog_t, sec_prog = analyze_commit_progress(sec_data, step_size=step_size, warmup_skip=warmup_skip)
    fig, ax = plt.subplots(figsize=(8, 4))
    p1, = ax.plot(base_prog_t, base_prog, color=BASELINE_COLOR, linewidth=1.0, alpha=0.9)
    p2, = ax.plot(sec_prog_t, sec_prog, color=ALTERED_COLOR, linewidth=1.0, alpha=0.95)
    ax.set_title(_make_setup_subtitle('none', 0, 4, n_nodes), fontsize=11, pad=8)
    ax.yaxis.grid(True, color='lightgray', linestyle='-')
    ax.xaxis.grid(False)
    ax.set_xlim(0, duration - warmup_skip)
    ax.set_ylim(bottom=0)
    positions, labels = _make_xticks(duration, warmup_skip)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    ax.set_ylabel('Cumulative Commits', fontsize=12)
    ax.set_xlabel('Time (s)', fontsize=12)
    fig.legend([p1, p2], ['standard client (f=0)', 'secure client (redundancy=4)'], loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=2, frameon=False, fontsize=11)
    plt.tight_layout(rect=(0, 0, 1, 0.90))
    out = os.path.join(search_dir, 'commit_progress_byzantine.png')
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved {out}')


def plot_mode(search_dir, records, mode, family, window_size, step_size, warmup_skip, log_y, baseline_record=None):
    base = baseline_record or select_latest_matching(records, family, 'none', 0, 1)
    if base is None:
        raise RuntimeError(f'missing baseline none f=0 for family {family}')

    base_data = extract_and_parse(base['path'])
    duration = infer_duration(base_data)
    base_times, base_tps = analyze_timeline(base_data, window_size, step_size, warmup_skip)

    n_nodes = records[0]['n_nodes'] if records else '?'

    available_f = sorted(set(r['failures'] for r in records if r['mode'] == mode and r['redundancy'] == 1))

    per_f = {}
    for f in available_f:
        rec = select_latest_matching(records, family, mode, f, 1)
        if rec:
            alt_data = extract_and_parse(rec['path'])
            alt_times, alt_tps = analyze_timeline(alt_data, window_size, step_size, warmup_skip)
            per_f[f] = (alt_times, alt_tps, rec['path'])

    has_recovery = mode != 'crash-no-recovery'

    for f, (alt_times, alt_tps, _) in per_f.items():
        fig, ax = plt.subplots(figsize=(8, 4))
        lb, = ax.plot(base_times, base_tps, color=BASELINE_COLOR, linewidth=0.9, alpha=0.9, label='baseline')
        la, = ax.plot(alt_times, alt_tps, color=ALTERED_COLOR, linewidth=0.9, alpha=0.95, label=f'{mode} f={f}')
        lf, lr = add_fault_recovery_lines(ax, duration, warmup_skip, has_recovery)
        ax.set_title(_make_setup_subtitle(mode, f, 1, n_nodes), fontsize=11, pad=8)
        _format_axes(ax, duration, warmup_skip, log_y)
        if has_recovery:
            fig.legend([lb, la, lf, lr], ['baseline', f'byzantine (f={f})', 'failures', 'recovery'], loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=4, frameon=False, fontsize=11)
        else:
            fig.legend([lb, la, lf], ['baseline', f'byzantine (f={f})', 'failures'], loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=3, frameon=False, fontsize=11)
        plt.tight_layout(rect=(0, 0, 1, 0.92))
        out = os.path.join(search_dir, f'plot_{mode}_f{f}.png')
        plt.savefig(out, dpi=300, bbox_inches='tight')
        plt.close(fig)
        print(f'Saved {out}')

    if per_f:
        ordered = sorted(per_f.keys())
        fig, axes = plt.subplots(2, 2, figsize=(16, 8), sharey=True, sharex=True)
        axes = axes.flatten()
        h1 = None
        h2 = None
        h3 = None
        h4 = None
        for i, f in enumerate(ordered[:4]):
            ax = axes[i]
            alt_times, alt_tps, _ = per_f[f]
            h1, = ax.plot(base_times, base_tps, color=BASELINE_COLOR, linewidth=0.9, alpha=0.9, label='baseline')
            h2, = ax.plot(alt_times, alt_tps, color=ALTERED_COLOR, linewidth=0.9, alpha=0.95, label=f'f={f}')
            h3, h4 = add_fault_recovery_lines(ax, duration, warmup_skip, has_recovery)
            ax.set_title(f'f={f}', fontsize=12)
            _format_axes(ax, duration, warmup_skip, log_y)
            if i % 2 == 1:
                ax.set_ylabel('')

        for j in range(len(ordered), 4):
            axes[j].axis('off')

        if h1 is not None and h2 is not None and h3 is not None and h4 is not None:
            if has_recovery:
                fig.legend([h1, h2, h3, h4], ['baseline', f'byzantine ({mode})', 'failures', 'recovery'], loc='upper center', bbox_to_anchor=(0.5, 1.02), ncol=4, frameon=False, fontsize=12)
            else:
                fig.legend([h1, h2, h3], ['baseline', f'byzantine ({mode})', 'failures'], loc='upper center', bbox_to_anchor=(0.5, 1.02), ncol=3, frameon=False, fontsize=12)
        fig.suptitle(_make_setup_subtitle(mode, ordered[0] if ordered else 0, 1, n_nodes), fontsize=11, y=1.02, color='#555555', style='italic')
        plt.tight_layout(rect=(0, 0, 1, 0.95))
        out = os.path.join(search_dir, f'plot_{mode}_f_all.png')
        plt.savefig(out, dpi=300, bbox_inches='tight')
        plt.close(fig)
        print(f'Saved {out}')

        base_prog_t, base_prog = analyze_commit_progress(base_data, step_size=step_size, warmup_skip=warmup_skip)

        for f, (_, _, path) in per_f.items():
            alt_data = extract_and_parse(path)
            alt_prog_t, alt_prog = analyze_commit_progress(alt_data, step_size=step_size, warmup_skip=warmup_skip)
            fig, ax = plt.subplots(figsize=(8, 4))
            p1, = ax.plot(base_prog_t, base_prog, color=BASELINE_COLOR, linewidth=1.0, alpha=0.9, label='baseline')
            p2, = ax.plot(alt_prog_t, alt_prog, color=ALTERED_COLOR, linewidth=1.0, alpha=0.95, label=f'byzantine (f={f})')
            p3, p4 = add_fault_recovery_lines(ax, duration, warmup_skip, has_recovery)
            ax.set_title(_make_setup_subtitle(mode, f, 1, n_nodes), fontsize=11, pad=8)
            ax.yaxis.grid(True, color='lightgray', linestyle='-')
            ax.xaxis.grid(False)
            ax.set_xlim(0, duration - warmup_skip)
            ax.set_ylim(bottom=0)
            positions, labels = _make_xticks(duration, warmup_skip)
            ax.set_xticks(positions)
            ax.set_xticklabels(labels)
            ax.set_ylabel('Cumulative Commits', fontsize=12)
            ax.set_xlabel('Time (s)', fontsize=12)
            if has_recovery:
                fig.legend([p1, p2, p3, p4], ['baseline', f'byzantine (f={f})', 'failures', 'recovery'], loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=4, frameon=False, fontsize=11)
            else:
                fig.legend([p1, p2, p3], ['baseline', f'byzantine (f={f})', 'failures'], loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=3, frameon=False, fontsize=11)
            plt.tight_layout(rect=(0, 0, 1, 0.92))
            out = os.path.join(search_dir, f'commit_progress_{mode}_f{f}.png')
            plt.savefig(out, dpi=300, bbox_inches='tight')
            plt.close(fig)
            print(f'Saved {out}')

        fig, axes = plt.subplots(2, 2, figsize=(16, 8), sharey=True, sharex=True)
        axes = axes.flatten()
        c1 = c2 = c3 = c4 = None
        for i, f in enumerate(ordered[:4]):
            ax = axes[i]
            alt_data = extract_and_parse(per_f[f][2])
            alt_prog_t, alt_prog = analyze_commit_progress(alt_data, step_size=step_size, warmup_skip=warmup_skip)
            c1, = ax.plot(base_prog_t, base_prog, color=BASELINE_COLOR, linewidth=1.0, alpha=0.9)
            c2, = ax.plot(alt_prog_t, alt_prog, color=ALTERED_COLOR, linewidth=1.0, alpha=0.95)
            c3, c4 = add_fault_recovery_lines(ax, duration, warmup_skip, has_recovery)
            ax.set_title(f'f={f}', fontsize=12)
            ax.yaxis.grid(True, color='lightgray', linestyle='-')
            ax.xaxis.grid(False)
            ax.set_xlim(0, duration - warmup_skip)
            ax.set_ylim(bottom=0)
            positions, labels = _make_xticks(duration, warmup_skip)
            ax.set_xticks(positions)
            ax.set_xticklabels(labels)
            ax.set_xlabel('Time (s)', fontsize=12)
            if i % 2 == 0:
                ax.set_ylabel('Cumulative Commits', fontsize=12)
            else:
                ax.set_ylabel('')

        for j in range(len(ordered), 4):
            axes[j].axis('off')

        if c1 is not None and c2 is not None and c3 is not None and c4 is not None:
            if has_recovery:
                fig.legend([c1, c2, c3, c4], ['baseline', f'byzantine ({mode})', 'failures', 'recovery'], loc='upper center', bbox_to_anchor=(0.5, 1.02), ncol=4, frameon=False, fontsize=12)
            else:
                fig.legend([c1, c2, c3], ['baseline', f'byzantine ({mode})', 'failures'], loc='upper center', bbox_to_anchor=(0.5, 1.02), ncol=3, frameon=False, fontsize=12)
        fig.suptitle(_make_setup_subtitle(mode, ordered[0] if ordered else 0, 1, n_nodes), fontsize=11, y=1.02, color='#555555', style='italic')
        plt.tight_layout(rect=(0, 0, 1, 0.95))
        out = os.path.join(search_dir, f'commit_progress_{mode}_f_all.png')
        plt.savefig(out, dpi=300, bbox_inches='tight')
        plt.close(fig)
        print(f'Saved {out}')
    else:
        print(f'Warning: no tarballs found for mode={mode}, family={family}')


def main():
    parser = argparse.ArgumentParser(description='Plot baseline vs f-level comparisons per fault mode.')
    parser.add_argument('-d', '--dir', required=True, help='Directory containing .results.tar.gz files (non-recursive)')
    parser.add_argument('--window', type=float, default=5.0)
    parser.add_argument('--step', type=float, default=1.0)
    parser.add_argument('--warmup-skip', type=float, default=0.0)
    parser.add_argument('--linear-y', action='store_true')
    parser.add_argument('--blockchain-family', choices=['hotstuff', 'asonnino-hotstuff'], default=None)
    parser.add_argument('--mode', choices=['crash', 'crash-no-recovery', 'partition', 'byzantine', 'all'], default='all')
    args = parser.parse_args()

    search_dir = os.path.abspath(args.dir)
    tarballs = sorted(glob.glob(os.path.join(search_dir, '*.results.tar.gz')))
    if not tarballs:
        raise SystemExit(f'No .results.tar.gz files found in {search_dir}')

    records = []
    for path in tarballs:
        parsed = parse_tarball_name(path)
        if parsed is None:
            continue
        bc, n_nodes, mode, f, r = parsed
        records.append({'path': path, 'blockchain': bc, 'n_nodes': n_nodes, 'mode': mode, 'failures': f, 'redundancy': r})

    family = choose_family(records, args.blockchain_family)
    baseline_record = select_latest_matching(records, family, 'none', 0, 1)
    if baseline_record is None:
        global_tarballs = sorted(glob.glob(os.path.join(os.path.dirname(search_dir), '*.results.tar.gz')))
        global_records = []
        for path in global_tarballs:
            parsed = parse_tarball_name(path)
            if parsed is None:
                continue
            bc, n_nodes, mode, f, r = parsed
            global_records.append({'path': path, 'blockchain': bc, 'n_nodes': n_nodes, 'mode': mode, 'failures': f, 'redundancy': r})
        baseline_record = select_latest_matching(global_records, family, 'none', 0, 1)

    if args.mode == 'byzantine':
        plot_byzantine_mode(search_dir, records, family, args.window, args.step, args.warmup_skip, not args.linear_y)
        return

    modes = ['crash', 'crash-no-recovery', 'partition'] if args.mode == 'all' else [args.mode]
    for mode in modes:
        plot_mode(search_dir, records, mode, family, args.window, args.step, args.warmup_skip, not args.linear_y, baseline_record=baseline_record)


if __name__ == '__main__':
    main()
