FROM dockerops/dockerops-common 
MAINTAINER Stefano Alberto Russo <stefano.russo@gmail.com>


#----------------------------
# Setup the DNS update
#----------------------------

RUN apt-get update #20162103 last update, change date to invalidate cache

COPY update_dns.sh /
RUN apt-get -y install dnsutils && \
    chmod 755 /update_dns.sh && \
    echo '/update_dns.sh' >> /entrypoint-local.sh && \
    chmod 755 /entrypoint-local.sh

#----------------------
# Startup
#----------------------

ENTRYPOINT ["/entrypoint-common.sh"]








