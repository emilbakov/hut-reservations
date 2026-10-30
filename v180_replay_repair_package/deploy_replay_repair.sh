#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
python3 v180_replay_repair_package/install_replay_repair.py --verify-staged
bash v180_deposit_flow_package/deploy_v180.sh
python3 v180_replay_repair_package/install_replay_repair.py --verify-installed
