#!/bin/bash
# Live tracker for section chunks + curated concepts background tasks
# Run: bash scripts/track_background_tasks.sh

SECTION_LOG="/private/tmp/claude-501/-Users-ankit1609-Desktop-3ioNetra-3ionetra/2b1d0d9f-5180-42bf-bd9b-2299bbe3c26c/tasks/bpontb8qw.output"
CURATED_LOG="/private/tmp/claude-501/-Users-ankit1609-Desktop-3ioNetra-3ionetra/2b1d0d9f-5180-42bf-bd9b-2299bbe3c26c/tasks/bifjsd4ay.output"

SECTION_DONE=false
CURATED_DONE=false

while true; do
    clear
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║       3ioNetra RAKS Pipeline — Background Task Tracker     ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    NOW=$(date '+%H:%M:%S')
    echo "  Last refresh: $NOW    (auto-refreshes every 10s, Ctrl+C to exit)"
    echo ""

    # --- Section Chunks ---
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ -f "/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/data/processed/sections_embeddings.npy" ]; then
        SECTION_DONE=true
        SIZE=$(ls -lh /Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/data/processed/sections_embeddings.npy | awk '{print $5}')
        CHUNKS=$(python3 -c "import json; d=json.load(open('/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/data/processed/sections.json')); print(len(d.get('sections',[])))" 2>/dev/null || echo "?")
        echo "  SECTION CHUNKS:  COMPLETE"
        echo "    Chunks: $CHUNKS"
        echo "    Embeddings: $SIZE"
    elif [ -f "$SECTION_LOG" ]; then
        LATEST=$(tail -1 "$SECTION_LOG" 2>/dev/null | tr '\r' '\n' | tail -1)
        # Extract progress
        PCT=$(echo "$LATEST" | grep -oE '[0-9]+%' | tail -1)
        BATCH=$(echo "$LATEST" | grep -oE '[0-9]+/374' | tail -1)
        ETA=$(echo "$LATEST" | grep -oE '[0-9]+:[0-9]+:[0-9]+' | tail -1)
        if [ -n "$PCT" ]; then
            # Build progress bar
            PCT_NUM=$(echo "$PCT" | tr -d '%')
            FILLED=$((PCT_NUM / 2))
            EMPTY=$((50 - FILLED))
            BAR=$(printf "%${FILLED}s" | tr ' ' '#')$(printf "%${EMPTY}s" | tr ' ' '-')
            echo "  SECTION CHUNKS:  RUNNING"
            echo "    [$BAR] $PCT"
            echo "    Batches: $BATCH    ETA: $ETA"
        else
            echo "  SECTION CHUNKS:  STARTING..."
            echo "    $LATEST"
        fi
    else
        echo "  SECTION CHUNKS:  NOT STARTED"
    fi
    echo ""

    # --- Curated Concepts ---
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ -f "/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/data/raw/curated_concepts_generated.json" ]; then
        CURATED_DONE=true
        COUNT=$(python3 -c "import json; d=json.load(open('/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/data/raw/curated_concepts_generated.json')); print(len(d))" 2>/dev/null || echo "?")
        echo "  CURATED CONCEPTS:  COMPLETE"
        echo "    Concepts generated: $COUNT"
    elif [ -f "$CURATED_LOG" ]; then
        # Get last 3 lines for context
        LINES=$(tail -3 "$CURATED_LOG" 2>/dev/null | tr '\r' '\n' | grep -v '^$' | tail -3)
        # Detect current category
        CATEGORY=$(tail -20 "$CURATED_LOG" 2>/dev/null | grep "^Category:" | tail -1)
        echo "  CURATED CONCEPTS:  RUNNING"
        if [ -n "$CATEGORY" ]; then
            echo "    $CATEGORY"
        fi
        echo "$LINES" | while read -r line; do
            echo "    $line"
        done

        # Count completed categories
        CATS_DONE=$(tail -200 "$CURATED_LOG" 2>/dev/null | grep -c "^Category:")
        echo "    Categories: $CATS_DONE/8"
    else
        echo "  CURATED CONCEPTS:  NOT STARTED"
    fi
    echo ""

    # --- Summary ---
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if $SECTION_DONE && $CURATED_DONE; then
        echo "  ALL TASKS COMPLETE"
        echo ""
        echo "  Next steps:"
        echo "    1. Review curated concepts: data/raw/curated_concepts_generated.json"
        echo "    2. Ingest: python scripts/ingest_all_data.py"
        echo "    3. Restart backend to pick up new data"
        break
    elif $SECTION_DONE; then
        echo "  Section chunks DONE, waiting for curated concepts..."
    elif $CURATED_DONE; then
        echo "  Curated concepts DONE, waiting for section chunks..."
    else
        echo "  Both tasks running..."
    fi
    echo ""

    sleep 10
done
