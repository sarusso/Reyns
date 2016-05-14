FROM dockerops/dockerops-common-ubuntu_14.04
MAINTAINER Stefano Alberto Russo <stefano.russo@gmail.com>

#----------------------------
# Setup the DNS update
#----------------------------
# Install dnsutils
RUN apt-get update #20162903 last update, change date to invalidate cache
RUN apt-get -y install dnsutils


COPY update-dns.sh /
RUN chmod 755 /update-dns.sh

#-----------------------
# Entrypoint
#-----------------------
# Copy, give right permissions & unique name to container entrypoint
COPY entrypoint-base.sh /entrypoints/
RUN chmod 755 /entrypoints/entrypoint-base.sh
RUN mv /entrypoints/entrypoint-base.sh /entrypoints/entrypoint-base-$(date +%s).sh





