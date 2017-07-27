FROM ubuntu:14.04
MAINTAINER Stefano Alberto Russo <stefano.russo@gmail.com>

#----------------------
# Basic packages
#----------------------

# Update
RUN apt-get update

# Utilities
RUN apt-get install -y nano
RUN apt-get install -y telnet
RUN apt-get install -y unzip
RUN apt-get install -y wget
RUN apt-get install -y supervisor

# Devel
RUN apt-get install -y build-essential
RUN apt-get install -y python-dev
RUN apt-get install -y git-core

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
RUN useradd reyns -u 65527 -g 65527 -m -s /bin/bash

# Add reyns user to sudoers
RUN adduser reyns sudo

# Keys
RUN mkdir /home/reyns/.ssh
COPY keys/authorized_keys /home/reyns/.ssh/
COPY keys/id_rsa /home/reyns/.ssh/
RUN chmod 0600 /home/reyns/.ssh/id_rsa
COPY keys/id_rsa.pub /home/reyns/.ssh/
RUN chown -R reyns:reyns /home/reyns/.ssh

# No pass sudo (for everyone, actually)
COPY common/sudoers /etc/sudoers

# bash_profile for loading correct env (/env.sh created by entrypoint.sh)
RUN echo "source /env.sh" > /home/reyns/.bash_profile

#------------------------
# Data, Logs and opt dirs
#------------------------

# Create dirs
RUN mkdir /data
RUN mkdir /opt/reyns
RUN mkdir /var/log/reyns 

# Give right permissions
RUN chown -R reyns:reyns /data
RUN chown -R reyns:reyns /opt/reyns
RUN chown -R reyns:reyns /var/log/reyns


#----------------------
#  Supervisord conf
#----------------------

COPY common/supervisord.conf /etc/supervisor/


#----------------------
# SSH service
#----------------------

RUN apt-get install -y openssh-server
RUN mkdir /var/run/sshd
RUN chmod 0755 /var/run/sshd
COPY common/supervisord_sshd.conf /etc/supervisor/conf.d/


#----------------------
# Startup scripts
#----------------------

# Create directory for startup scripts
RUN mkdir /startup

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








