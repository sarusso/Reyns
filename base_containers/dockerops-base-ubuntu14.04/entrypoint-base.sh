#!/bin/bash

if [[ "x$CONTAINER" == "xdns" ]] ; then
    exit 0
fi

if [[ "x$DNS_CONTAINER_IP" == "x" ]] ; then
    echo "WARNING: Empty DNS_CONTAINER_IP env var: disabling DockerOps dynamic DNS"
    exit 0
fi

if [[ "x$DNSLINK_ON_IP" == "x" ]] ; then
    IP=$(ip addr show eth0 | grep -F inet | grep -vF inet6 | awk '{print $2}' | rev | cut -c 4- | rev | tr -d \\n)
else
    IP=$DNSLINK_ON_IP
fi

cat > /mydnsdata << __EOT__
server $DNS_CONTAINER_IP
zone local.zone
update delete `hostname`.local.zone. A
update add `hostname`.local.zone. 86400 A $IP
show
send
__EOT__

# Update DNS
/update-dns.sh $DNS_CONTAINER_IP &> /var/log/update-dns.log &
