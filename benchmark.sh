#!/bin/bash

set -e

SKIP_BUILD=""
E2E_ONLY=""

if [[ "$1" == "--skip-build" ]]; then
    SKIP_BUILD="--skip-build"
    shift
fi

if [[ "$1" == "--e2e-only" ]]; then
    E2E_ONLY="true"
    shift
fi

DATA_DIR=${HOME}/data
SETUP_E2E="setups/setup-10-2.txt"

mkdir ${HOME}/data

cd ${HOME}/minion

if [[ -z "$E2E_ONLY" ]]; then

    # none
    mkdir -p ${HOME}/data/none
    ./bin/middleware $SKIP_BUILD workloads/workload-transfer-200-5-algorand.yaml setups/setup-10.txt algorand none 0 1 2>&1 | tee algorand-none.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt aptos none 0 1 2>&1 | tee aptos-none.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt avalanche none 0 1 2>&1 | tee avalanche-none.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt sevm none 0 1 2>&1 | tee sevm-none.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt solana none 0 1 2>&1 | tee solana-none.log
    mv *.results.tar.gz *.log ${HOME}/data/none

    # resilience
    mkdir -p ${HOME}/data/resilience
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5-algorand.yaml setups/setup-10.txt algorand crash-no-recovery 2 1 2>&1 | tee algorand-crash-no-recovery.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt aptos crash-no-recovery 3 1 2>&1 | tee aptos-crash-no-recovery.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt avalanche crash-no-recovery 2 1 2>&1 | tee avalanche-crash-no-recovery.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt sevm crash-no-recovery 3 1 2>&1 | tee sevm-crash-no-recovery.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt solana crash-no-recovery 3 1 2>&1 | tee solana-crash-no-recovery.log
    mv *.results.tar.gz *.log ${HOME}/data/resilience

    # recoverability
    mkdir -p ${HOME}/data/recoverability
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5-algorand.yaml setups/setup-10.txt algorand crash 3 1 2>&1 | tee algorand-crash.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt aptos crash 4 1 2>&1 | tee aptos-crash.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt avalanche crash 3 1 2>&1 | tee avalanche-crash.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt sevm crash 4 1 2>&1 | tee sevm-crash.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt solana crash 4 1 2>&1 | tee solana-crash.log
    mv *.results.tar.gz *.log ${HOME}/data/recoverability

    # partition
    mkdir -p ${HOME}/data/partition
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5-algorand.yaml setups/setup-10.txt algorand partition 3 1 2>&1 | tee algorand-partition.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt aptos partition 4 1 2>&1 | tee aptos-partition.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt avalanche partition 3 1 2>&1 | tee avalanche-partition.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt sevm partition 4 1 2>&1 | tee sevm-partition.log
    ./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5.yaml setups/setup-10.txt solana partition 4 1 2>&1 | tee solana-partition.log
    mv *.results.tar.gz *.log ${HOME}/data/partition

fi

# e2e_none
mkdir -p ${HOME}/data/e2e_none
./bin/middleware --skip-build workloads/workload-transfer-200-5-4-algorand.yaml "$SETUP_E2E" algorand none 0 1 2>&1 | tee algorand-none-1.log
./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5-4.yaml "$SETUP_E2E" aptos none 0 1 2>&1 | tee aptos-none-1.log
./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5-4.yaml "$SETUP_E2E" avalanche none 0 1 2>&1 | tee avalanche-none-1.log
./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5-4.yaml "$SETUP_E2E" sevm none 0 1 2>&1 | tee sevm-none-1.log
./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5-4.yaml "$SETUP_E2E" solana none 0 1 2>&1 | tee solana-none-1.log
mv *.results.tar.gz *.log ${HOME}/data/e2e_none

# e2e
mkdir -p ${HOME}/data/e2e
./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5-4-algorand.yaml "$SETUP_E2E" algorand none 0 4 2>&1 | tee algorand-none-4.log
./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5-4.yaml "$SETUP_E2E" aptos none 0 4 2>&1 | tee aptos-none-4.log
./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5-4.yaml "$SETUP_E2E" avalanche none 0 4 2>&1 | tee avalanche-none-4.log
./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5-4.yaml "$SETUP_E2E" sevm none 0 4 2>&1 | tee sevm-none-4.log
./bin/middleware --skip-build --skip-install workloads/workload-transfer-200-5-4.yaml "$SETUP_E2E" solana none 0 4 2>&1 | tee solana-none-4.log
mv *.results.tar.gz *.log ${HOME}/data/e2e
