import os
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from pybatfish.client.session import Session
from pybatfish.datamodel import PathConstraints, HeaderConstraints

# -----------------------------
# Configuration & Setup
# -----------------------------
TAG = datetime.now().strftime("%Y%m%d_%H%M%S")
print(f"Tag is {TAG}")

BATFISH_HOST = os.environ.get("BATFISH_HOST", "172.23.71.245")
BATFISH_PORT = int(os.environ.get("BATFISH_PORT", 9996))

# Use Pathlib for cleaner directory management
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = (SCRIPT_DIR / ".." / ".." / "bf_snapshot").resolve()
OUTPUT_DIR = Path(os.environ.get("BATFISH_RESULTS_DIR", SCRIPT_DIR / ".." / ".." / "batfish_results")).resolve()

# -----------------------------
# 1. Connect & Load Snapshot
# -----------------------------
bf = Session(host=BATFISH_HOST, port=BATFISH_PORT)

print(f"🔍 Searching for snapshots in: {BASE_DIR}")
if not BASE_DIR.exists() or not BASE_DIR.is_dir():
    print("❌ Snapshot directory missing.")
    exit(1)

# Get list of directories inside BASE_DIR
snapshots = [d for d in BASE_DIR.iterdir() if d.is_dir()]
if not snapshots:
    print("❌ No snapshots found.")
    exit(1)

# Find the most recently modified snapshot directory
latest_snapshot = max(snapshots, key=lambda d: d.stat().st_mtime)
print(f"\n📂 Loading snapshot: {latest_snapshot}")

bf.init_snapshot(str(latest_snapshot), name="ospf_lab", overwrite=True)

# -----------------------------
# Parse Check
# -----------------------------
parse_issues = bf.q.initIssues().answer().frame()
if not parse_issues.empty:
    print("\n⚠️ Parse Issues Found:")
    print(parse_issues)
else:
    print("\n✅ Snapshot clean - No parse issues.")

# -----------------------------
# 2. RUN ANALYSIS QUERIES
# -----------------------------
print("\nRunning Batfish Queries...")

# Reachability Query
reach = pd.DataFrame()
try:
    reach_answer = bf.q.reachability(
        # Changed h1 and h3 to r1 and r3
        pathConstraints=PathConstraints(startLocation="r1", endLocation="r3"),
        headers=HeaderConstraints(dstIps="192.168.1.0/24,192.168.2.0/24,192.168.3.0/24")
    ).answer()
    
    # Safely check if it has a frame (meaning it didn't return a server error)
    if hasattr(reach_answer, 'frame'):
        reach = reach_answer.frame()
    else:
        print("⚠️ Reachability query failed on the server (check node names).")
        reach = pd.DataFrame()

except Exception as e:
    print(f"⚠️ Reachability script error: {e}")
    reach = pd.DataFrame()
# OSPF and Routes Queries
try:
    ospf_neighbors = bf.q.ospfSessionCompatibility().answer().frame()
    routes = bf.q.routes().answer().frame()
except Exception as e:
    print(f"⚠️ Failed to pull OSPF or routing tables: {e}")
    ospf_neighbors = pd.DataFrame()
    routes = pd.DataFrame()

print("\n--- OSPF Neighbors ---")
print(ospf_neighbors if not ospf_neighbors.empty else "No OSPF Neighbors found.")

# -----------------------------
# 3. COMPUTE METRICS
# -----------------------------
unreachable_routes = pd.DataFrame()
loops = pd.DataFrame()
blackholes = pd.DataFrame()
ospf_failures = pd.DataFrame()
static_routes = pd.DataFrame()
static_failures = pd.DataFrame()

# Process Reachability (Blackholes, Loops, Unreachability)
if not reach.empty and "Traces" in reach.columns:
    traces = reach["Traces"].astype(str).str.upper()
    
    unreachable_routes = reach[traces.str.contains("DROP|DENY|NULL_ROUTED|NO_ROUTE", regex=True)]
    loops = reach[traces.str.contains("LOOP")]
    blackholes = reach[traces.str.contains("BLACKHOLE")]

# Process OSPF Failures
if not ospf_neighbors.empty and "Session_Status" in ospf_neighbors.columns:
    ospf_failures = ospf_neighbors[ospf_neighbors["Session_Status"].astype(str).str.upper() != "ESTABLISHED"]

# Process Routes (Static Routes & assumed Static Failures)
if not routes.empty and "Protocol" in routes.columns:
    static_routes = routes[routes["Protocol"].astype(str).str.upper() == "STATIC"]

# Currently defining static failures as any dropped reachability trace
static_failures = unreachable_routes

# -----------------------------
# 4. RISK SCORE CALCULATION
# -----------------------------
risk_score = (
    len(static_failures) * 3 +
    len(loops) * 5 +
    len(blackholes) * 4 +
    len(ospf_failures) * 3
)

if risk_score == 0:
    risk_level = "GOOD"
elif risk_score <= 6:
    risk_level = "MEDIUM"
else:
    risk_level = "HIGH"

# -----------------------------
# 5. REPORT GENERATION
# -----------------------------
output = {
    "unreachable_routes": len(unreachable_routes),
    "static_failures": len(static_failures),
    "loops": len(loops),
    "blackholes": len(blackholes),
    "ospf_failures": len(ospf_failures),
    "static_routes": len(static_routes),  
    "risk_score": risk_score,
    "risk_level": risk_level
}

print("\n===== NETWORK RISK REPORT =====")
print(json.dumps(output, indent=2))

# Display OSPF Process Info
print("\n--- OSPF Process Configuration ---")
try:
    ospf_process = bf.q.ospfProcessConfiguration().answer().frame()
    if not ospf_process.empty and all(col in ospf_process.columns for col in ["Node", "Areas"]):
        print(ospf_process[["Node", "Areas"]])
    else:
        print("No OSPF process configurations found.")
except Exception as e:
    print(f"⚠️ Failed to pull OSPF processes: {e}")

# -----------------------------
# 6. EXPORT DATASET
# -----------------------------
csv_dir = OUTPUT_DIR / "csv"
json_dir = OUTPUT_DIR / "json"

# Create directories safely
csv_dir.mkdir(parents=True, exist_ok=True)
json_dir.mkdir(parents=True, exist_ok=True)

df_export = pd.DataFrame([output])

# Save individual CSV
csv_path = csv_dir / f"network_risk_dataset_{TAG}.csv"
df_export.to_csv(csv_path, index=False)
print(f"\n💾 Saved individual CSV -> {csv_path}")

# Append to or create Master CSV
master_csv = OUTPUT_DIR / "batfish_ml_dataset.csv"
if master_csv.exists():
    df_export.to_csv(master_csv, mode="a", header=False, index=False)
else:
    df_export.to_csv(master_csv, index=False)
print(f"📈 Updated master dataset -> {master_csv}")

# Save JSON Report
json_path = json_dir / f"risk_{TAG}.json"
with open(json_path, "w") as f:
    json.dump(output, f, indent=2)
print(f"💾 Saved JSON report -> {json_path}")
