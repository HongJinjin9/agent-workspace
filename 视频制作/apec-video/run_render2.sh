#!/bin/bash
cd /app/vedio/apec-video
python3 -u scene3d.py "$1" "$2" >> /tmp/apec3d-render-$1.log 2>&1
echo "done $1 $2" >> /tmp/apec3d-render-$1.log
