FROM dockerops/dockerops-base-ubuntu_14.04
MAINTAINER Stefano Alberto Russo <stefano.russo@gmail.com>

#----------------------
# Demo Stuff
#----------------------

#RUN apt-get install -y somepackage

# Copy, give right permissions & unique name to container entrypoint
COPY entrypoint-demo.sh /entrypoints/
RUN chmod 755 /entrypoints/entrypoint-demo.sh
RUN mv /entrypoints/entrypoint-demo.sh /entrypoints/entrypoint-demo-$(date +%s).sh

















