# Stabl: The Sensitivity of Blockchains to Failures (Minion Framework)

This repository contains **Minion**, the experiment orchestration framework used for the paper *"Stabl: The Sensitivity of Blockchains to Failures"* (Middleware 2025).

This guide explains how to configure and run the framework on **your own cluster of machines**.

## Prerequisites

### Hardware
To reproduce the experiments, you need a cluster of Linux machines (physical or virtual) accessible via SSH.
*   **Orchestrator:** 1 machine (can be your local machine).
*   **Blockchain Nodes:** At least 10 nodes (recommended: 4 vCPUs, 8GB+ RAM).
*   **Diablo Nodes:** At least 5 nodes.

### Software
*   **OS:** Ubuntu 22.04 LTS (recommended).
*   **Perl:** v5.34.0 or higher.
*   **Network:** All nodes must communicate with each other. The orchestrator must be able to SSH into all nodes without a password (using SSH keys).
*   **Sudo:** The user running the scripts on the worker nodes needs passwordless sudo access (required for `tc` network manipulation).

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/lebdron/minion.git
   cd minion
   ```

2. **Install Perl Dependencies:**
   Use `cpanminus` to install the required libraries.
   ```bash
   sudo apt-get install cpanminus
   cpanm -n YAML JSON
   ```

## Configuration (Crucial Steps)

To run this on your own hardware, you **must** update the hardcoded network interface settings and IP addresses in specific files.

### 1. Update Network Interface (`eth2`)
The scripts default to using `eth2` for network traffic analysis and fault injection (packet dropping). If your machines use a different interface (e.g., `eth0`, `ens3`, `enp4s0`), you must update the following files:

*   **File:** `lib/Minion/Ssh.pm`
    *   **Action:** Find the line containing `ip -4 -o a show eth2`.
    *   **Change:** Replace `eth2` with your cluster's public-facing network interface.
    ```perl
    # Example change for 'eth0'
    my $ret = $self->execute([ 'ip', '-4', '-o', 'a', 'show', 'eth0' ], STDOUT => \$out)->wait();
    ```

*   **File:** `observer.py`
    *   **Action:** This script uses `tc` (Traffic Control) to simulate partitions. Find all instances of `eth2`.
    *   **Change:** Replace `eth2` with your network interface in all `subprocess.run` calls.
    ```python
    # Example change:
    subprocess.run(shlex.split("sudo tc qdisc add dev eth0 root handle 1: prio"))
    ```

### 2. Configure Node Inventory (`setups/`)
You need to define your cluster topology. Create or modify a file in the `setups/` directory (e.g., `setups/my-cluster.txt`).

**Format:** `ssh_user@ip_address = role1,role2,...`

**Roles:**
*   `primary`: The Diablo benchmark controller (usually 1 node).
*   `secondary`: Diablo nodes that send transactions.
*   `chain`: Nodes running the blockchain software.
*   `builder`: Node responsible for compiling blockchain binaries.

**Example `setups/my-cluster.txt`:**
```text
ubuntu@192.168.1.10 = chain
ubuntu@192.168.1.11 = chain
# ... add remaining chain nodes ...
ubuntu@192.168.1.50 = primary,secondary
ubuntu@192.168.1.51 = secondary
ubuntu@192.168.1.60 = builder
```

### 3. Configure Workloads (`workloads/`)
The workload YAML files define how transactions are sent. They contain **Regex** patterns to map client load to specific node IP addresses. You must update these to match the IPs used in your setup file.

Open the workload file you intend to run (e.g., `workloads/workload-transfer-200-5.yaml`) and modify the `sample: !location` and `sample: !endpoint` fields.

**Example:**
If your setup file uses IPs `192.168.1.x`, change the Regex:
```yaml
# OLD (from repo)
- &l-1  { sample: !location [ "10\\.40\\.20\\.1$"  ] }

# NEW (your IPs)
- &l-1  { sample: !location [ "192\\.168\\.1\\.51$"  ] }
```
*Note: Ensure you escape dots (`\\.`) in the IP addresses because these strings are interpreted as Regular Expressions.*

### 4. Disable Redbelly
The Redbelly Blockchain (referenced as `sevm` in the scripts) is not currently publicly available. You must manually disable it in the source code to prevent installation errors.

1.  **Edit `bin/middleware`**:
    Open the file `bin/middleware` and locate the `sub install` function. Comment out the following two lines to prevent the script from looking for missing binaries:
    ```perl
    # install_archive($fleet, 'binaries/sevm.tar.gz', 'install/sevm');
    # install_archive($fleet, 'binaries/sevm-prepare.tar.gz', 'prepare/sevm/network-10-10000');
    ```

2.  **Edit `benchmark.sh`**:
    Open `benchmark.sh` and comment out or delete all lines invoking the middleware for `sevm`. For example:
    ```bash
    # ./bin/middleware ... sevm none 0 1 ...
    ```

## Usage

The main entry point for running experiments is `benchmark.sh`.

### Running the Benchmark

```bash
./benchmark.sh [options]
```

**Options:**
*   `--skip-build`: Skips the compilation of blockchain binaries. Use this only if you have already run the script once successfully.
*   `--e2e-only`: Runs only the Byzantine node tolerance (end-to-end) scenarios (located at the bottom of the script).

Results are saved in the `~/data` directory as .tar.gz archives containing transaction logs and metrics.

**First Run:**
On the very first execution, run the script **without arguments**:
```bash
./benchmark.sh
```
This will automatically connect to the `builder` node defined in your setup file, compile all blockchain binaries, install them on the worker nodes, and then begin the experiments.

### Understanding `benchmark.sh`

The `benchmark.sh` script is a wrapper around the core `./bin/middleware` executable. You can look at `benchmark.sh` to see how to construct custom commands.

You should modify the `SETUP_E2E` variable or the hardcoded setup paths inside `benchmark.sh` to point to your specific `setups/my-cluster.txt` file.

**Manual Execution Example:**
If you wish to run a specific experiment manually (without the full suite), use the command structure found in `benchmark.sh`:

```bash
./bin/middleware [options] <workload-file> <ip-file> <blockchain> <failure-mode> <num-failures> <redundancy>
```

*   **`<workload-file>`**: Path to YAML workload (e.g., `workloads/workload-transfer-200-5.yaml`).
*   **`<ip-file>`**: Path to your setup file.
*   **`<blockchain>`**: `algorand`, `aptos`, `avalanche`, `sevm` (Redbelly), or `solana`.
*   **`<failure-mode>`**: `none` (baseline), `crash`, `partition`, `crash-no-recovery`.
*   **`<num-failures>`**: Number of nodes to fail (e.g., `3`).
*   **`<redundancy>`**: Client redundancy factor (usually `1`).

**Note:** If you run `./bin/middleware` manually, the build process will trigger automatically unless you pass `--skip-build` or `--skip-install`.
