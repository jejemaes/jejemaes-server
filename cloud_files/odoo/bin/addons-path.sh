#!/usr/bin/env bash
BRANCH=$1
CUSTOM="$HOME/src/custom"
THEMES="$HOME/src/themes"
ENTERPRISE="$HOME/src/enterprise"
ADDONS="$CUSTOM/default,$HOME/src/odoo/$BRANCH/addons"
WORKER_ADDONS=web$(find "$CUSTOM/default" -maxdepth 1 -type d -name '*_worker' -printf ',%f')

MODES=$(jq -r .me.mode "$HOME/config/config.json" 2>/dev/null) || true

if [[ -d "$THEMES/$BRANCH" ]]; then
    ADDONS="$ADDONS,$THEMES/$BRANCH"
fi
if [[ -d "$ENTERPRISE/$BRANCH" ]]; then
    ADDONS="$ENTERPRISE/$BRANCH,$ADDONS"    # enterprise repo must be in first place
fi
for m in $MODES; do
    if [ -d "$CUSTOM/$m" ]; then
        ADDONS="$CUSTOM/$m,$ADDONS"
        # each addons ending with '_worker' is considered as a worker to load
        WORKER_ADDONS="$WORKER_ADDONS"$(find "$CUSTOM/$m" -maxdepth 1 -type d -name '*_worker' -printf ',%f')
    fi;
done;
