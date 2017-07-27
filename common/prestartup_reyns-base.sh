#!/bin/bash

if [[ "x$SERVICE" == "xdns" ]] ; then
    exit 0
fi

if [[ "x$DNS_SERVICE_IP" == "x" ]] ; then
    echo "WARNING: Empty DNS_SERVICE_IP env var: disabling Reyns dynamic DNS"
    exit 0
fi

if [[ "x$SERVICE_IP" == "x" ]] ; then
    IP=$(ip addr show eth0 | grep -F inet | grep -vF inet6 | awk '{print $2}' | rev | cut -c 4- | rev | tr -d \\n)
else
    IP=$SERVICE_IP
fi

if [[ "x$DNS_UPDATE_POLICY" == "xHIDE" ]] ; then
# Update DNS resolv only
                cp /etc/resolv.conf /etc/resolv.conf.bak
                cat > /etc/resolv.conf << __EOT__
search local.zone
nameserver $DNS_SERVICE_IP
__EOT__
    exit 0
fi

if [[ "x$DNS_UPDATE_POLICY" == "xAPPEND" ]] ; then
cat > /mydnsdata << __EOT__
server $DNS_SERVICE_IP
zone local.zone
update delete `hostname`.local.zone. A
update add `hostname`.local.zone. 60 A $IP
update add `echo $SERVICE`.local.zone. 60 A $IP
show
send
__EOT__
else
cat > /mydnsdata << __EOT__
server $DNS_SERVICE_IP
zone local.zone
update delete `hostname`.local.zone. A
update delete `echo $SERVICE`.local.zone. A
update add `hostname`.local.zone. 60 A $IP
update add `echo $SERVICE`.local.zone. 60 A $IP
show
send
__EOT__
fi





# Update DNS
/update-dns.sh $DNS_SERVICE_IP &> /var/log/update-dns.log &
