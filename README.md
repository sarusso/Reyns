**WARNING: this is alpha software under heavy development. First beta release is foreseen for October 2015.**

If you are interested in contributing please drop me a line at stefano.russo@gmail.com.


DockerOps
===

Simple yet powerful Docker operations orchestratorfor managing entire platforms. Allows to speed up both Dev (every developer can run its own instance of the platform) and Ops (what is put in production is deterministically tested before). 

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

`fab build:all` (Several minutes, use fab build:all,progress=True for verbose output)

`fab run:all` (Whatever value is fine for HOST_FQDN)

`fab ps`

`fab ssh:demo`

`ssh $BASE_IP_ADDRESS` (in the Docker)

`exit` (in the Docker)

`exit` (in the Docker)

`fab clean.all`
