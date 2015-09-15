**WARNING: this is alpha software under heavy development.**  
**First beta release is foreseen for October 2015.**

If you are interested in contributing please drop me a line at stefano.russo@gmail.com.


DockerOps
===

Simple yet powerful Docker operations orchestrator for managing entire platforms. Allows to speed up both Dev (every developer can run its own instance of the platform) and Ops (what is put in production is deterministically tested before). 

Prerequisites
---

Docker, Fabric (apt-get install fabric)


Documentation
---

Coming soon

Quick start
---

`git clone https://github.com/sarusso/DockerOps.git`

`cd DockerOps`

`./install.sh`

Exit and re-open terminal

`dockerops build:all` (Several minutes, use `dockerops build:all,progress=True` for verbose output)

`dockerops run:all` (Whatever value is fine for HOST_FQDN)

`dockerops ps`

`dockerops ssh:demo`

`ssh $BASE_CONTAINER_IP` (in the Docker, you are now connecting to the base Docker)

`exit` (in the base Docker)

`exit` (in the demo Docker)

`dockerops clean:all`
