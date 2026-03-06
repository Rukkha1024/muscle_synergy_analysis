#!/bin/bash

# Simple GPU Monitor - Shows basic nvidia-smi output every 1 second
# This is the most reliable way to monitor GPU usage in WSL2

echo "Simple GPU Monitor - Press Ctrl+C to stop"
echo "=========================================="

# Basic nvidia-smi monitoring with 1-second updates
watch -n 1 nvidia-smi