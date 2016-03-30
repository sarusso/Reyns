#!/bin/bash

if [[ "x$CONTAINER" == "xdns" ]] ; then
    exit 0
fi

if [[ "x$DNS_CONTAINER_IP" == "x" ]] ; then
    echo "WARNING: Empty DNS_CONTAINER_IP env var: disabling DockerOps dynamic DNS"
    exit 0
fi

if [[ "x$INSTANCE_TYPE" == "xmaster" ]] || [[ "x$INSTANCE_TYPE" == "xpublished" ]]; then
    if [[ "x$HOST_IP" == "x" ]] ; then
        echo "CRITICAL: Empty HOST_IP env var, required when instance is in master or published mode and the DNS_CONTAINER_IP var is set."
        exit 1
    fi
    IP=$HOST_IP
else
    IP=$(ip addr show eth0 | grep -F inet | grep -vF inet6 | awk '{print $2}' | rev | cut -c 4- | rev | tr -d \\n)
fi

cat > /mydnsdata << __EOT__
server $DNS_CONTAINER_IP
zone local.zone
update delete `hostname`.local.zone. A
update add `hostname`.local.zone. 86400 A $IP
show
send
__EOT__



# Update DNS (if up)

# First check that the DNS is set and reachable
while true
do
    ping -c1 "$DNS_CONTAINER_IP"
    OUT_STATE=$?
    if [[ $OUT_STATE -ne 0 ]] ; then
        echo "Could not reach DNS on $DNS_CONTAINER_IP, sleeping 60 seconds and retrying..."
        sleep 60
    else
        # Ok,proceed
        
/usr/bin/nsupdate -k /etc/rndc.key -v /mydnsdata 2>&1 | tee /var/log/nsupdate.log && \
cp /etc/resolv.conf /etc/resolv.conf.bak && \
cat > /etc/resolv.conf << __EOT__
search local.zone
nameserver $DNS_CONTAINER_IP
__EOT__
         break
     fi
done
























