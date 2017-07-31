FROM ubuntu:14.04
MAINTAINER Stefano Alberto Russo <stefano.russo@gmail.com>

#----------------------
# Basic packages
#----------------------

# Update
RUN apt-get update

# Utilities
RUN apt-get install -y nano telnet unzip wget supervisor openssh-server

# Devel
RUN apt-get install -y build-essential python-dev git-core

# Java
RUN apt-get install -y openjdk-7-jre

# Generate missing US locale
RUN locale-gen en_US en_US.UTF-8


#------------------------
# Reyns user
#------------------------

# Add group. We chose GID 65527 to try avoiding conflicts.
RUN groupadd -g 65527 reyns

# Add user. We chose UID 65527 to try avoiding conflicts.
RUN useradd reyns -d /reyns -u 65527 -g 65527 -m -s /bin/bash

# Add reyns user to sudoers
RUN adduser reyns sudo

# Keys
RUN mkdir /reyns/.ssh
COPY keys/authorized_keys /reyns/.ssh/
COPY keys/id_rsa /reyns/.ssh/
RUN chmod 0600 /reyns/.ssh/id_rsa
COPY keys/id_rsa.pub /reyns/.ssh/
RUN chown -R reyns:reyns /reyns/.ssh

# No pass sudo (for everyone, actually)
COPY common/sudoers /etc/sudoers

# bash_profile for loading correct env (/env.sh created by entrypoint.sh)
RUN echo "source /env.sh" > /reyns/.bash_profile

#------------------------
# Data, Logs and opt dirs
#------------------------

# Create dirs
RUN mkdir /data && mkdir /opt/reyns && mkdir /var/log/reyns 

# Give right permissions
RUN chown -R reyns:reyns /data && chown -R reyns:reyns /opt/reyns && chown -R reyns:reyns /var/log/reyns


#----------------------
#  Supervisord conf
#----------------------

COPY common/supervisord.conf /etc/supervisor/


#----------------------
# SSH conf
#----------------------

RUN mkdir /var/run/sshd && chmod 0755 /var/run/sshd
COPY common/supervisord_sshd.conf /etc/supervisor/conf.d/


#----------------------
# Prestartup scripts
#----------------------

# Create dir for prestartup scripts and copy main script
RUN mkdir /prestartup
COPY common/prestartup.py /

#----------------------------
# Generate DNS key
#----------------------------
RUN apt-get -y install bind9utils && \
    rndc-confgen | head -n 5 > /etc/rndc.key && \
    chmod 600 /etc/rndc.key

#----------------------
# Entrypoint
#----------------------

# Copy entrypoint
COPY common/entrypoint.sh /

# Give right permissions
RUN chmod 755 /entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]








