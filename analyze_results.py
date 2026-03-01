#!/usr/bin/env python3
import json
import sys
import os
import tarfile
from tempfile import TemporaryDirectory

def analyze_results(filepath):
    print(f"Analyzing {os.path.basename(filepath)}...\n")
    
    # Extract json data
    data = None
    if filepath.endswith('.tar.gz'):
        with tarfile.open(filepath, 'r:gz') as tar:
            for member in tar.getmembers():
                if member.name.endswith('results.json'):
                    f = tar.extractfile(member)
                    if f is not None:
                        data = json.loads(f.read().decode('utf-8'))
                    break
    elif filepath.endswith('.json'):
        with open(filepath, 'r') as f:
            data = json.load(f)
            
    if not data:
        print("Could not find results.json in the provided path")
        sys.exit(1)

    # Initialize stats
    total_txs = 0
    committed = 0
    aborted = 0
    errors = 0
    
    # Latency tracking
    latencies = []
    
    # Throughput tracking (group by second)
    txs_per_sec = {}
    commits_per_sec = {}
    
    # Process all interactions
    for loc in data.get('Locations', []):
        for client in loc.get('Clients', []):
            for ix in client.get('Interactions', []):
                total_txs += 1
                
                # Times in results.json are actually in seconds (float)
                submit_time = ix.get('SubmitTime', -1)
                commit_time = ix.get('CommitTime', -1)
                abort_time = ix.get('AbortTime', -1)
                has_error = ix.get('HasError', False)
                
                if has_error:
                    errors += 1
                    
                # Throughput bucket (by second)
                sec_bucket = int(submit_time)
                txs_per_sec[sec_bucket] = txs_per_sec.get(sec_bucket, 0) + 1
                
                if commit_time > 0:
                    committed += 1
                    # Convert latency to milliseconds for display
                    latency = (commit_time - submit_time) * 1000
                    latencies.append(latency)
                    
                    commit_sec_bucket = int(commit_time)
                    commits_per_sec[commit_sec_bucket] = commits_per_sec.get(commit_sec_bucket, 0) + 1
                    
                elif abort_time > 0:
                    aborted += 1

    # Calculate summaries
    print("=== SUMMARY ===")
    print(f"Total Transactions: {total_txs}")
    print(f"Committed:          {committed} ({(committed/total_txs*100) if total_txs else 0:.1f}%)")
    print(f"Aborted:            {aborted} ({(aborted/total_txs*100) if total_txs else 0:.1f}%)")
    print(f"Errors:             {errors}")
    print("")

    if latencies:
        latencies.sort()
        avg_lat = sum(latencies) / len(latencies)
        p50 = latencies[int(len(latencies) * 0.5)]
        p90 = latencies[int(len(latencies) * 0.9)]
        p99 = latencies[int(len(latencies) * 0.99)]
        
        print("=== LATENCY (ms) ===")
        print(f"Average: {avg_lat:.1f}")
        print(f"P50:     {p50:.1f}")
        print(f"P90:     {p90:.1f}")
        print(f"P99:     {p99:.1f}")
        print("")

    print("=== THROUGHPUT (TPS over time) ===")
    if not txs_per_sec:
        print("No transactions recorded.")
        return

    min_sec = min(txs_per_sec.keys())
    max_sec = max(txs_per_sec.keys())
    
    # We aggregate into 20-second buckets for display to avoid too many lines
    bucket_size = max(1, (max_sec - min_sec) // 20)
    
    current_bucket_start = min_sec
    while current_bucket_start <= max_sec:
        bucket_end = current_bucket_start + bucket_size - 1
        
        submitted_in_bucket = sum(txs_per_sec.get(s, 0) for s in range(current_bucket_start, bucket_end + 1))
        committed_in_bucket = sum(commits_per_sec.get(s, 0) for s in range(current_bucket_start, bucket_end + 1))
        
        # Calculate actual average TPS for this bucket
        avg_submit_tps = submitted_in_bucket / bucket_size
        avg_commit_tps = committed_in_bucket / bucket_size
        
        # Only print buckets that have activity
        if submitted_in_bucket > 0 or committed_in_bucket > 0:
            time_label = f"[{current_bucket_start - min_sec:03d}s - {bucket_end - min_sec:03d}s]"
            print(f"{time_label} Submitted: {avg_submit_tps:5.1f} TPS | Committed: {avg_commit_tps:5.1f} TPS")
            
        current_bucket_start += bucket_size

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_results.py <results.tar.gz or results.json>")
        sys.exit(1)
        
    analyze_results(sys.argv[1])
