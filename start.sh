#!/bin/bash
# start.sh — Start Flask app and serveo tunnel together

echo "Starting Flask app..."
python app.py &
FLASK_PID=$!

echo "Waiting for Flask to start..."
sleep 3

echo "Starting serveo tunnel..."
ssh -o StrictHostKeyChecking=no -R 80:localhost:5000 serveo.net 2>&1 | tee tunnel.log &

sleep 4

echo ""
echo "========================================="
echo "PUBLIC LINK:"
grep -o 'https://[^ ]*' tunnel.log
echo "========================================="
echo ""
echo "Flask PID: $FLASK_PID"
echo "Press Ctrl+C to stop everything"

wait
