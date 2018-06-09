#!/usr/bin/env bash
BRANCH=$1
ADDONS="$HOME/src/odoo/$BRANCH/addons"
WORKER_ADDONS=web

declare -a REPOS=("jejemaes" "enterprise" "oca")

for m in $$REPOS; do
    if [ -d "$HOME/src/$m" ]; then
        ADDONS="$HOME/src/$m,$ADDONS"
        # each addons ending with '_worker' is considered as a worker to load
        WORKER_ADDONS="$WORKER_ADDONS"$(find "$HOME/src/$m" -maxdepth 1 -type d -name '*_worker' -printf ',%f')
    fi;
done;
