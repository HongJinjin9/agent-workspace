#!/bin/bash
cd /app/vedio/ep03-judgment && exec python3 -u scene_judgment.py --range "$1" "$2"
