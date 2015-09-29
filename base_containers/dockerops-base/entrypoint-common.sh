#!/bin/bash
set -e

echo "Excecuting common entrypoint"

#-------------------
#   Save env
#-------------------
echo " Dumping env..."

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
echo " Handling peristency..."

# If persistent data:
if [ "$PERSISTENT_DATA" = "True" ]; then
    echo " Persistent data set"
    if [ ! -f /persistent/data/.persistent_initialized ]; then
        mv /data /persistent/data
        ln -s /persistent/data /data
        touch /data/.persistent_initialized
    else
       mkdir -p /trash
       mv /data /trash
       ln -s /persistent/data /data
    fi
fi

# If persistent log:
if [ "$PERSISTENT_LOG" = "True" ]; then
    echo " Persistent log set"
    if [ ! -f /persistent/log/.persistent_initialized ]; then
        mv /var/log /persistent/log
        ln -s /persistent/log /var/log
        touch /var/log/.persistent_initialized
    else
       mkdir -p /trash
       mv /var/log /trash
       ln -s /persistent/log /var/log
    fi
fi

# If persistent opt:
if [ "$PERSISTENT_OPT" = "True" ]; then
    echo " Persistent opt set"
    if [ ! -f /persistent/opt/.persistent_initialized ]; then
        mv /opt /persistent/opt
        ln -s /persistent/opt /opt
        touch /opt/.persistent_initialized
    else
       mkdir -p /trash
       mv /opt /trash
       ln -s /persistent/opt /opt
    fi
fi





#-------------------
#  Entrypoint
#-------------------

echo "Now executing container's entrypoint"
echo ""

exec /entrypoint.sh "$@"




