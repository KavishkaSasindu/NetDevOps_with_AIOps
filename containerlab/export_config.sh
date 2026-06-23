#!/bin/bash

OUT_DIR="configs"
mkdir -p $OUT_DIR

echo "🚀 Auto-detecting router containers..."

CONTAINERS=$(docker ps --format "{{.Names}}" | grep "^r")

for router in $CONTAINERS
do
    echo "📡 Extracting from $router"

    docker exec $router vtysh -c "show running-config" > "$OUT_DIR/$router.conf"

    echo "✅ Saved $router.conf"
done

echo "🎯 Done."
