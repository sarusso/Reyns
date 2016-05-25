FROM dockerops/dockerops-common-ubuntu14.04
MAINTAINER Gianfranco Gallizia <gianfranco.gallizia@exact-lab.it>

# Update
RUN apt-get update #20160403 last update, change date to invalidate cache

#-----------------------
# Install bind package
#-----------------------
RUN apt-get -y install bind9 && \
    mkdir -p /var/cache/bind && \
    chown root:bind /var/cache/bind && \
    mkdir -p /var/run/named && \
    chmod 777 /var/run/named

#-----------------------
# Install rndc.key file 
#-----------------------
RUN install -m 640 -o root -g bind /etc/rndc.key /etc/bind/rndc.key

#-----------------------
# Copy the db zone files
#-----------------------
COPY db.* /etc/bind/
RUN chown root:bind /etc/bind/db.local.zone /etc/bind/db.rev.local.zone && \
    chmod 640 /etc/bind/db.local.zone /etc/bind/db.rev.local.zone && \
    ln -s /etc/bind/db.local.zone /var/cache/bind/db.local.zone && \
    ln -s /etc/bind/db.rev.local.zone /var/cache/bind/db.rev.local.zone

#-----------------------
# Copy named.conf.local
#-----------------------
COPY named.conf.local /etc/bind/

#-----------------------
# supervisord - bind
#-----------------------
COPY supervisord_bind.conf /etc/supervisor/conf.d/
COPY runbind.sh /
RUN chmod 755 /runbind.sh

#-----------------------
# Entrypoint
#-----------------------
# Copy, give right permissions & unique name to container entrypoint
COPY entrypoint-dns.sh /entrypoints/
RUN chmod 755 /entrypoints/entrypoint-dns.sh
RUN mv /entrypoints/entrypoint-dns.sh /entrypoints/entrypoint-dns-$(date +%s).sh

