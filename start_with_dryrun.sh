#!/bin/bash
# Startup script to activate DRYRUN mode
export PCA_MODE=DRYRUN
echo "🚀 Starting FinBrain with PCA_MODE=DRYRUN"
echo "   All users will generate CCs with zero impact"
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app