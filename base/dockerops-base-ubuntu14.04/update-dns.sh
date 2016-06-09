#!/bin/bash
DNS_SERVICE_IP=$1
while true
do
    # Check that the DNS is set and reachable
    ping -c1 "$DNS_SERVICE_IP"
    OUT_STATE=$?
    if [[ $OUT_STATE -ne 0 ]] ; then
        echo "Could not ping DNS on $DNS_SERVICE_IP, sleeping 1 seconds and retrying..."
        sleep 1
    else
        # Ok,proceed
        while true
        do
            # Try to update the DNS entry
            /usr/bin/nsupdate -k /etc/rndc.key -v /mydnsdata 2>&1 || OUT_STATE=1

            # Check for correct update and break if successful
            if [[ $OUT_STATE -ne 0 ]] ; then
                echo "Could not update DNS on $DNS_SERVICE_IP, sleeping 3 seconds and retrying..."
                sleep 3
            else
                # Update DNS resolv
                cp /etc/resolv.conf /etc/resolv.conf.bak
                cat > /etc/resolv.conf << __EOT__
search local.zone
nameserver $DNS_SERVICE_IP
__EOT__
                break
            fi
        done
        break
     fi
done