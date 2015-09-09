#!/bin/bash
set -e

# Call common entrypoint
/docker-entrypoint-common.sh

# Start!
exec "$@"
