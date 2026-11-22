#!/bin/sh
export TH_KEY="$(jq -r '.api_key // ""' /data/options.json)"
export TH_IFACE="$(jq -r '.interface // ""' /data/options.json)"
exec /usr/bin/thnet
