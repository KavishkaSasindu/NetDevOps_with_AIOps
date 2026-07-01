from pybatfish.client.session import Session
from pybatfish.datamodel import PathConstraints, HeaderConstraints
from datetime import datetime
import pandas as pd
import json
import os


tag = datetime.now().strftime("%Y%m%d_%H%M%S")
print(f"tag is {tag}")

# -----------------------------
# 1. Connect to Batfish
# -----------------------------

bf = Session(host="172.23.71.245", port=9996)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "..", "bf_snapshot")
)

print(f"🔍 Searching for snapshots in absolute path: {BASE_DIR}")

if not os.path.exists(BASE_DIR):
    print("Snapshot directory missing")
    exit(1)

snapshots = [
    os.path.join(BASE_DIR, d)
    for d in os.listdir(BASE_DIR)
    if os.path.isdir(os.path.join(BASE_DIR, d))
]

if not snapshots:
    print("No snapshots found")
    exit(1)

latest_snapshot = max(
    snapshots,
    key=os.path.getmtime
)


SNAPSHOT_DIR = latest_snapshot

print(f"\n📂 Loading snapshot: {SNAPSHOT_DIR}")
bf.init_snapshot(
    SNAPSHOT_DIR,
    name="ospf_lab",
    overwrite=True
)

# -----------------------------
# Parse Check
# -----------------------------

parse_issues = bf.q.initIssues().answer().frame()
if not parse_issues.empty:
    print("\n⚠️ Parse Issues:")
    print(parse_issues)
else:
    print("\n✅ Snapshot clean")

# -----------------------------
# 2. RUN ANALYSIS
# -----------------------------

print("Running Batfish Queries...")

# Test LAN reachability through static routes
try:
    reach_answer = bf.q.reachability(
        pathConstraints=PathConstraints(
            startLocation="h1",
            endLocation="h3"
        ),
        headers=HeaderConstraints(
            dstIps="192.168.3.1"
        )
    ).answer()
    reach = reach_answer.frame()


except Exception as e:
    print(
        f"⚠️ Reachability skipped: {e}"
    )
    reach = pd.DataFrame()

ospf_neighbors = (
    bf.q.ospfSessionCompatibility()
    .answer()
    .frame()
)


routes = (
    bf.q.routes()
    .answer()
    .frame()
)

print("\n--- OSPF Neighbors ---")

print(ospf_neighbors)

# -----------------------------
# 3. METRICS
# -----------------------------

unreachable_routes = pd.DataFrame()
loops = pd.DataFrame()
blackholes = pd.DataFrame()


if not reach.empty and "Traces" in reach.columns:
    traces = (
        reach["Traces"]
        .astype(str)
        .str.upper()
    )

    unreachable_routes = reach[
        traces.str.contains(
            "DROP|DENY|NULL_ROUTED|NO_ROUTE"
        )
    ]

    loops = reach[
        traces.str.contains(
            "LOOP"
        )
    ]
    blackholes = reach[
        traces.str.contains(
            "BLACKHOLE"
        )
    ]

# OSPF failures

ospf_failures = pd.DataFrame()
if "Session_Status" in ospf_neighbors.columns:
    ospf_failures = ospf_neighbors[
        ospf_neighbors["Session_Status"]
        !=
        "ESTABLISHED"
    ]

# Static routes only informational

static_routes = pd.DataFrame()

if "Protocol" in routes.columns:
    static_routes = routes[
        routes["Protocol"]
        .astype(str)
        .str.upper()
        ==
        "STATIC"
    ]

# Static failure detection
# If static route exists but reachability fails

static_failures = unreachable_routes

# -----------------------------
# 4. RISK SCORE
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
# 5. REPORT
# -----------------------------

output = {
    "unreachable_routes":len(unreachable_routes),
    "static_failures":len(static_failures),
    "loops":len(loops),
    "blackholes":len(blackholes),
    "ospf_failures":len(ospf_failures),
    "static_routes_detected":len(static_routes),
    "risk_score":risk_score,
    "risk_level":risk_level
}

print(
    "\n===== NETWORK RISK REPORT ====="
)
print(
    json.dumps(
        output,
        indent=2
    )
)

# OSPF process

print("\n--- OSPF Process ---")
ospf_process = (
    bf.q.ospfProcessConfiguration()
    .answer()
    .frame()
)

if not ospf_process.empty:

    print(
        ospf_process[
            [
                "Node",
                "Areas"
            ]
        ]
    )

# -----------------------------
# 6. EXPORT DATASET
# -----------------------------

OUTPUT_DIR = os.environ.get(
    "BATFISH_RESULTS_DIR",
    os.path.abspath(
        os.path.join(
            SCRIPT_DIR,
            "..",
            "..",
            "batfish_results"
        )
    )
)

os.makedirs(
    f"{OUTPUT_DIR}/csv",
    exist_ok=True
)

os.makedirs(
    f"{OUTPUT_DIR}/json",
    exist_ok=True
)

df_export = pd.DataFrame(
    [output]
)

csv_path = (
    f"{OUTPUT_DIR}/csv/"
    f"network_risk_dataset_{tag}.csv"
)

df_export.to_csv(
    csv_path,
    index=False
)

print(
    f"\n💾 Saved CSV -> {csv_path}"
)

master_csv = (
    f"{OUTPUT_DIR}/batfish_ml_dataset.csv"
)

if os.path.exists(master_csv):
    df_export.to_csv(
        master_csv,
        mode="a",
        header=False,
        index=False
    )

else:
    df_export.to_csv(
        master_csv,
        index=False
    )

print(
    f"📈 Updated dataset -> {master_csv}"
)

json_path = (
    f"{OUTPUT_DIR}/json/"
    f"risk_{tag}.json"
)

with open(json_path, "w") as f:
    json.dump(
        output,
        f,
        indent=2
    )

print(
    f"💾 Saved JSON -> {json_path}"
)
