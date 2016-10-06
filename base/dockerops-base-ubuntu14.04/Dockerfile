FROM dockerops/dockerops-common-ubuntu14.04
MAINTAINER Stefano Alberto Russo <stefano.russo@gmail.com>

#----------------------------
# Setup the DNS update
#----------------------------
# Install dnsutils
RUN apt-get update
RUN apt-get -y install dnsutils


COPY update-dns.sh /
RUN chmod 755 /update-dns.sh

#-----------------------
# Prestartup
#-----------------------
COPY prestartup_dockerops-base.sh /prestartup/






