#!/bin/bash
set -e

# Get forward IP
if [[ "x$INSTANCE_TYPE" == "xmaster" ]] ; then
    if [[ "x$HOST_IP" == "x" ]] ; then
        echo "CRITICAL: Empty HOST_IP env var, check conf"
        exit 1
    fi
    FWDIP=$HOST_IP
else
    FWDIP=$(ip addr show eth0 | grep -F inet | grep -vF inet6 | awk '{print $2}' | rev | cut -c 4- | rev | tr -d \\n)
fi

# Reverse it
REVIP=`echo $FWDIP | awk -F. '{printf("%s.%s.%s.%s.in-addr.arpa.", $4, $3, $2, $1)}'`

REVZONEDEF=`echo $FWDIP | awk -F. '{printf("%s.%s.in-addr.arpa", $2, $1)}'`

#Edit /etc/bind/db.local.zone
sed -i.bak -e "s/FWDIP/$FWDIP/" -- /etc/bind/db.local.zone

#Edit /etc/bind/db.rev.local.zone
sed -i.bak -e "s/REVIP/$REVIP/" -- /etc/bind/db.rev.local.zone

#Fix /etc/bind/named.conf.local
sed -i.bak -e "s/QQQ/$REVZONEDEF/" -- /etc/bind/named.conf.local
