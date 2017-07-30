FROM centos:7.2.1511
MAINTAINER Stefano Alberto Russo <stefano.russo@gmail.com>

#----------------------
# Basic packages
#----------------------

# Install yum overlay plugin for supporting docker and update
RUN yum install yum-plugin-ovl -y 
RUN yum update -y

# Utilities
RUN yum install -y nano telnet unzip wget
RUN yum install -y epel-release # https://gist.github.com/tanksuzuki/cbef7abfa70888895534
RUN yum install -y supervisor

# Devel
RUN yum groupinstall -y 'Development Tools'
RUN yum install -y python-devel git-core

# Java
RUN yum install -y java-1.7.0-openjdk # https://www.digitalocean.com/community/tutorials/how-to-install-java-on-centos-and-fedora

# Generate missing US locale
#RUN locale-gen en_US en_US.UTF-8


#------------------------
# Reyns user
#------------------------

# Add group. We chose GID 65527 to try avoiding conflicts.
RUN groupadd -g 65527 reyns

# Add user. We chose UID 65527 to try avoiding conflicts.
RUN useradd reyns -u 65527 -g 65527 -m -s /bin/bash

# Install sudo for allowing reyns to do sudo
RUN yum install -y sudo 

# Keys
RUN mkdir /home/reyns/.ssh
COPY keys/authorized_keys /home/reyns/.ssh/
COPY keys/id_rsa /home/reyns/.ssh/
RUN chmod 0600 /home/reyns/.ssh/id_rsa
COPY keys/id_rsa.pub /home/reyns/.ssh/
RUN chown -R reyns:reyns /home/reyns/.ssh

# No pass sudo (for everyone, actually)
COPY common/sudoers-centos /etc/sudoers

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
RUN rm /etc/supervisord.conf  && ln -s /etc/supervisor/supervisord.conf /etc/supervisord.conf 


#----------------------
# SSH service
#----------------------

RUN yum install -y openssh-server
RUN mkdir /var/run/sshd
RUN chmod 0755 /var/run/sshd
COPY common/supervisord_sshd.conf /etc/supervisor/conf.d/
RUN ssh-keygen -A # https://bbs.archlinux.org/viewtopic.php?id=165382


#----------------------
# Startup scripts
#----------------------

# Create directory for startup scripts
RUN mkdir /startup

#----------------------------
# Generate DNS key
#----------------------------
# http://rhel-7.blogspot.co.uk/2014/10/dns-installation-and-configuration-for.html
RUN yum -y install bind* && \ 
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








