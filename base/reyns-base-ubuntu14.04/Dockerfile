FROM reyns/reyns-common-ubuntu14.04
MAINTAINER Stefano Alberto Russo <stefano.russo@gmail.com>

#----------------------------
# Setup the DNS update
#----------------------------
# Install dnsutils
RUN apt-get update
RUN apt-get -y install dnsutils


COPY common/update-dns.sh /
RUN chmod 755 /update-dns.sh

#-----------------------
# Prestartup
#-----------------------
COPY common/prestartup_reyns-base.sh /prestartup/






