#!/bin/bash
# 单镜渲染入口：./run_render.sh <shot_id>；或用 scene_body.py --all --jobs 2
cd /app/vedio/ep04-body && exec python3 -u scene_body.py --shot "$1"
