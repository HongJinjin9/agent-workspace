#!/bin/bash
cd /app/vedio/ep01-hybrid
python3 -u scene_hybrid.py "$1" "$2" >> /tmp/ep01-render-$1.log 2>&1
echo "done $1 $2" >> /tmp/ep01-render-$1.log
