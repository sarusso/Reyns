DockerOps
===

Simple yet powerful Docker operations orchestrator

Prerequisites
---

Docker, Fabric (apt-get install fabric)


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
