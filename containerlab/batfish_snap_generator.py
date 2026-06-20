import os
import sys
from datetime import datetime

# -----------------------------
# 1. DYNAMIC SNAPSHOT NAMING
# -----------------------------
if len(sys.argv) > 1:
    snapshot_name = sys.argv[1]
else:
    snapshot_name = f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

CLAB_DIR = "."
SNAPSHOT_DIR = os.path.join(".", "bf_snapshot", snapshot_name)
CONFIGS_DIR = os.path.join(SNAPSHOT_DIR, "configs")

# -----------------------------
# 2. BUILD THE SNAPSHOT
# -----------------------------
routers = ["r1", "r2", "r3"]

for router in routers:
    source_file = os.path.join(CLAB_DIR, router, "frr.conf")
    os.makedirs(CONFIGS_DIR, exist_ok=True)
    target_file = os.path.join(CONFIGS_DIR, f"{router}.cfg")

    if not os.path.exists(source_file):
        print(f"⚠️ Could not find {source_file}. Did you run this from the clab folder?")
        continue

    with open(source_file, "r") as f:
        original_config = f.read()

    # THE ULTIMATE HEADER:
    # 1. Line 1 is the raw hostname (Defeats Cisco parser).
    # 2. Exact trigger string for the interfaces file.
    # 3. Explicitly defines eth1 and eth2 so OSPF can bind to them!
    batfish_header = f"""{router}
# This file describes the network interfaces
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet manual

auto eth1
iface eth1 inet manual

auto eth2
iface eth2 inet manual

# ports.conf --

# /etc/frr/frr.conf
frr version 8.4
hostname {router}
!
"""
    
    new_config = batfish_header + original_config

    with open(target_file, "w") as f:
        f.write(new_config)

    print(f"✅ Packaged: {router} -> {target_file}")

print(f"\n🚀 Snapshot is ready at: {SNAPSHOT_DIR}")
