FROM ubuntu:14.04
MAINTAINER Stefano Alberto Russo <stefano.russo@gmail.com>

#----------------------
# Basic packages
#----------------------

# Update
RUN apt-get update #20160429 last update, change date to invalidate cache

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
# DockerOps user
#------------------------

# Add usser
RUN useradd dockerops -m -s /bin/bash
RUN adduser dockerops sudo

# Keys
RUN mkdir /home/dockerops/.ssh
COPY keys/authorized_keys /home/dockerops/.ssh/
COPY keys/id_rsa /home/dockerops/.ssh/
RUN chmod 0600 /home/dockerops/.ssh/id_rsa
COPY keys/id_rsa.pub /home/dockerops/.ssh/
RUN chown -R dockerops:dockerops /home/dockerops/.ssh

# No pass sudo (for everyone, actually)
COPY sudoers /etc/sudoers

# bash_profile for loading correct env (/env.sh created by entrypoint.sh)
RUN echo "source /env.sh" > /home/dockerops/.bash_profile

#------------------------
# Data, Logs and opt dirs
#------------------------

# Create dirs
RUN mkdir /data
RUN mkdir /opt/dockerops
RUN mkdir /var/log/dockerops 

# Give right permissions
RUN chown -R dockerops:dockerops /data
RUN chown -R dockerops:dockerops /opt/dockerops
RUN chown -R dockerops:dockerops /var/log/dockerops


#----------------------
#  Supervisord conf
#----------------------

COPY supervisord.conf /etc/supervisor/


#----------------------
# SSH service
#----------------------

RUN apt-get install -y openssh-server
RUN mkdir /var/run/sshd
RUN chmod 0755 /var/run/sshd
COPY supervisord_sshd.conf /etc/supervisor/conf.d/


#----------------------
# Entrypoint files
#----------------------

# Create directory for containers entrypoints
RUN mkdir /entrypoints

# Copy seed entrypoint (and custom one)
COPY entrypoint.sh /

# Give right permissions
RUN chmod 755 /entrypoint.sh


#----------------------------
# Generate DNS key
#----------------------------
RUN apt-get -y install bind9utils && \
    rndc-confgen | head -n 5 > /etc/rndc.key && \
    chmod 600 /etc/rndc.key

#----------------------
# Startup
#----------------------

ENTRYPOINT ["/entrypoint.sh"]








