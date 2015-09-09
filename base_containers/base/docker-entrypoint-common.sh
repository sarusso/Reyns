#!/bin/bash
set -e

#-------------------
#   Save env
#-------------------

# Save env vars for in-container usage (e.g. ssh)

env | \
while read env_var; do
  if [[ $env_var == HOME\=* ]]; then
      : # Skip HOME var
  elif [[ $env_var == PWD\=* ]]; then
      : # Skip PWD var
  else
      echo "export $env_var" >> /env.sh
  fi
done


#-------------------
#   Persistency
#-------------------

# TODO...





