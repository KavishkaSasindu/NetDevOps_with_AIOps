from pybatfish.client.session import Session
from datetime import datetime
import pandas as pd
import json
import os

tag = datetime.now().strftime("%Y%m%d_%H%M%S")

# -----------------------------
# 1. Connect to Batfish
# -----------------------------
bf = Session(host="172.23.71.245", port=9996)

# This points to the parent folder holding all your generated snapshots
BASE_DIR = "../containerlab/bf_snapshot/"

# Find all directories inside BASE_DIR
snapshots = [
    os.path.join(BASE_DIR, d)
    for d in os.listdir(BASE_DIR)
    if os.path.isdir(os.path.join(BASE_DIR, d))
]

if not snapshots:
    print(f"❌ No snapshots found in {BASE_DIR}")
    exit(1)

# Pick the latest snapshot dynamically by modified time
latest_snapshot = max(snapshots, key=os.path.getmtime)

# Batfish requires the ROOT snapshot folder (e.g., snap_20260617_162144)
SNAPSHOT_DIR = latest_snapshot
print(f"\n📂 Loading latest snapshot: {SNAPSHOT_DIR}")

# Initialize the snapshot in PyBatfish
bf.init_snapshot(SNAPSHOT_DIR, name="ospf_lab", overwrite=True)

# Optional: Print parsing issues to ensure everything was read correctly
parse_issues = bf.q.initIssues().answer().frame()
if not parse_issues.empty:
    print("\n⚠️ Parse Issues Detected:")
    print(parse_issues)
else:
    print("\n✅ Snapshot loaded cleanly with no parsing errors.")

# -----------------------------
# 2. RUN ANALYSIS QUERIES
# -----------------------------
print("Running Batfish Queries...")

try:
    reach_answer = bf.q.reachability().answer()
    # Check if the answer actually contains tabular data (a frame)
    reach = reach_answer.frame() if hasattr(reach_answer, 'frame') else pd.DataFrame()
except Exception as e:
    print(f"⚠️ Reachability query skipped: {e}")
    reach = pd.DataFrame()
ospf = bf.q.ospfProcessConfiguration().answer().frame()
routes = bf.q.routes().answer().frame()

print("\n--- OSPF Neighbors ---")
ospf_neighbors = bf.q.ospfSessionCompatibility().answer().frame()
print(ospf_neighbors)

# -----------------------------
# 3. METRICS COLLECTION
# -----------------------------
unreachable_routes = reach[reach["Action"] == "FAILURE"] if "Action" in reach.columns else []
loops = reach[reach["Action"].str.contains("LOOP", na=False)] if "Action" in reach.columns else []
blackholes = reach[reach["Action"].str.contains("BLACKHOLE", na=False)] if "Action" in reach.columns else []

ospf_failures = []
ospf_failures = pd.DataFrame()
if "Session_Status" in ospf_neighbors.columns:
    ospf_failures = ospf_neighbors[ospf_neighbors["Session_Status"] != "ESTABLISHED"]

static_routes = routes[routes.get("Protocol", "").astype(str).str.upper() == "STATIC"] if "Protocol" in routes.columns else []

# -----------------------------
# 4. RISK MODEL (simple but CV-ready)
# -----------------------------
risk_score = (
    len(unreachable_routes) * 3 +
    len(loops) * 5 +
    len(blackholes) * 4 +
    len(ospf_failures) * 3 +
    len(static_routes) * 1
)

if risk_score <= 2:
    risk_level = "LOW"
elif risk_score <= 6:
    risk_level = "MEDIUM"
else:
    risk_level = "HIGH"

# -----------------------------
# 5. FINAL REPORT
# -----------------------------
output = {
    "unreachable_routes": len(unreachable_routes),
    "loops": len(loops),
    "blackholes": len(blackholes),
    "ospf_failures": len(ospf_failures),
    "static_routes": len(static_routes),
    "risk_score": risk_score,
    "risk_level": risk_level
}

print("\n===== NETWORK RISK REPORT =====")
print(json.dumps(output, indent=2))

print("\n--- Process Configuration ---")
df = bf.q.ospfProcessConfiguration().answer().frame()
if not df.empty:
    print(df[["Node", "Areas"]])
else:
    print("No OSPF process configurations found.")

# -----------------------------
# 6. EXPORT FOR ML DATASET
# -----------------------------
# Ensure the export directories exist
os.makedirs("../network_risk_dataset_snap/csv", exist_ok=True)
os.makedirs("../network_risk_dataset_snap/json", exist_ok=True)

csv_path = f"../network_risk_dataset_snap/csv/network_risk_dataset_{tag}.csv"
df_export = pd.DataFrame([output])
df_export.to_csv(csv_path, index=False)
print(f"\n💾 Saved CSV -> {csv_path}")

#Append data to ml_dataset
# Append to master ML dataset
master_csv = "../network_risk_dataset_snap/batfish_ml_dataset.csv"

if os.path.exists(master_csv):
    # Append without header
    df_export.to_csv(master_csv, mode="a", header=False, index=False)
else:
    # Create file with header
    df_export.to_csv(master_csv, mode="w", header=True, index=False)

print(f"📈 Appended data to -> {master_csv}")

json_path = f"../network_risk_dataset_snap/json/risk_{tag}.json"
with open(json_path, "w") as f:
    json.dump(output, f, indent=2)
print(f"💾 Saved JSON -> {json_path}")
