#!/bin/bash

echo ""
echo "[INFO] Executing Reyns entrypoint..."

#---------------------
#   Persistency
#---------------------

echo "[INFO] Handling safe persistency"
if [ "x$SAFE_PERSISTENCY" == "xTrue" ]; then
    echo "[INFO] Safe persistency set"
    if [ ! -f /safe_persistent/persistent.img ]; then
        truncate -s 10G /safe_persistent/persistent.img
        mkfs.ext4 -F /safe_persistent/persistent.img
    fi
    mkdir /persistent
    mount -oloop /safe_persistent/persistent.img /persistent
fi


echo "[INFO] Handling persistency"

# If persistent data:
if [ "x$PERSISTENT_DATA" == "xTrue" ]; then
    echo "[INFO] Persistent data set"
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
if [ "x$PERSISTENT_LOG" == "xTrue" ]; then
    echo "[INFO] Persistent log set"
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
if [ "x$PERSISTENT_OPT" == "xTrue" ]; then
    echo "[INFO] Persistent opt set"
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


#---------------------
#  Prestartup scripts
#---------------------

if [ "x$SAFEMODE" == "xFalse" ]; then
    echo "[INFO] Executing  prestartup scripts (current + parents):"
    python /prestartup.py
else
    echo "[INFO] Not executing prestartup scripts as we are in safemode"
fi


#---------------------
#   Save env
#---------------------
echo "[INFO] Dumping env"

# Save env vars for later usage (e.g. ssh)

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

#---------------------
#  Entrypoint command
#---------------------
# Start!
echo -n "[INFO] Executing Docker entrypoint command: "
echo $@
exec "$@"
