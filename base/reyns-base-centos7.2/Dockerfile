FROM reyns/reyns-common-centos7.2
MAINTAINER Stefano Alberto Russo <stefano.russo@gmail.com>

#----------------------------
# Setup the DNS update
#----------------------------
# Install dnsutils nto required, already instaleld in the common image
# RUN yum -y update
# RUN yum -y install bind-utils 


COPY common/update-dns.sh /
RUN chmod 755 /update-dns.sh

#-----------------------
# Prestartup
#-----------------------
COPY common/prestartup_reyns-base.sh /prestartup/






