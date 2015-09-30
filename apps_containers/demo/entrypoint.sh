#!/bin/bash
set -e

# Your entrypoint commands here, for example sed conf files to insert runtime IP adresses


# Start. DockerOps by default starts supervisord or bash if container is run in safemode.
# It is suggested not to change this logic, but if you really want you of course can.

exec "$@"