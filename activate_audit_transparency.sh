#!/bin/bash
# Activate Audit Transparency Feature
export PCA_OVERLAY_ENABLED=true
export PCA_MODE=ON
export SHOW_AUDIT_UI=true
export ENABLE_RULES=true
export USE_PRECEDENCE=true

echo "✅ Audit Transparency Feature Activated!"
echo "PCA_OVERLAY_ENABLED=$PCA_OVERLAY_ENABLED"
echo "PCA_MODE=$PCA_MODE"
echo "SHOW_AUDIT_UI=$SHOW_AUDIT_UI"

# Start the application with audit transparency enabled
exec "$@"