**WARNING: this is beta software under heavy development.**  

If you are interested in contributing please drop me a line at stefano.russo@gmail.com.


#DockerOps


Simple yet powerful Docker operations orchestrator for managing entire platforms. Allows to speed up both Dev (every developer can run its own instance of the platform) and Ops (what is put in production is deterministically tested before). 

## Prerequisites

Docker, Fabric (apt-get install fabric)


## Quick start and demo

`git clone https://github.com/sarusso/DockerOps.git`

`cd DockerOps`

`./install.sh`

Exit and re-open terminal

`dockerops build:all` (Several minutes, use `dockerops build:all,progress=True` for verbose output)

`dockerops run:all`

`dockerops ps`

`dockerops ssh:demo`

`ssh $BASE_CONTAINER_IP` (in the Docker, you are now connecting to the base Docker)

`exit` (in the base Docker)

`exit` (in the demo Docker)

`dockerops clean:all`



## Documentation


### Introduction and basics

DockerOps allows you to define how to build, run and interconnect a set (or from now on, a *project*) of Docker containers. It comes with a base container on which you should build all your Dockers, where Supervisor and SSH are installed and configured by default. The base container has a default user named "dockerops" which has the SSH keys for accessing every Docker container you create on top of the base container. Please not that in production you may want to change or remove the SSH keys.

A project is organized in folders: each Docker container must have its own folder and by default they have to be contained in a folder named "apps_containers". Inside the folder of a container, you have to place a Dockerfile wich starts with the line: 

	FROM your_project_name/dockerops-base

The basic usage relise on four very simple commands. Fisrt you build your congaiWhen running a Docker container, you just use a simple command: `dockerops run:your_container_name`. Once the container is started, you can ssh into is using `dockerops ssh:your_container_name`, and turn it off using dockerops `clean:your_container_name`

### Containers properties

When you run a Docker container using DockerOps, there are a few properties already implemented to make the life easier. These are:

* `linked`: linking enabled or not (according to the project's run.conf, see later)
* `publish_ports`: if set to true, publish the ports on the host according to the EXPOSE instruction in the Dockerfile
* `persistent_data`: if enabled, all the data in /data inside the container is made persistnt on the host filesystem (if data is already present, it is preserved) 
* `persistent_opt`: if enabled, all the data in /opt inside the containeris made persistnt on the host filesystem (if data is already present, it is preserved) 
* `persistent_log`: if enabled, all the data in /var/log inside the container is made persistnt on the host filesystem (if data is already present, it is preserved) 


### Instances
DockerOps introduces the concept of *instances* of the same Docker conatiner: this is just a naming convention and does not modify in any way how Docker works, but it is an extremely useful feature. For examle you can have a container running in two instances (i.e. nodeA and nodeB)

A DockerOps instance can be of four *instance types*: **standard**, **published**, **master**, **interactive** and **safemode**. The safemode and interactive instances types will be covered more in detail in thei section. The following table summarize the defaults properies for the instances types, but no one prevents you from specifying custom settings (command line arguments have the highest possible precedence in DockerOps)

| Instance type | linked | publish_ports | persistent_data | persisten_opt | persistent_log |
|---------------|:------:|--------------:|----------------:|--------------:|---------------:|
| standard      | YES    | NO            | NO              | NO            | YES            |  
| published     | YES    | YES           | NO              | NO            | NO             |
| master        | YES*   | YES           | YES             | NO            | NO             |
| interactive   | YES    | NO            | NO              | NO            | NO             |
| safemode      | NO     | NO            | NO              | NO            | NO             |


*the linking in an instance of type **master** require a proper setting of the env vars, as explained in the dedicated section.

There is also a rapid shortcut when running the containers: if you do not specify the instance type but you name an instance **master**, **published**, **interactive** or **safemode** the instance type will be set accordingly. Whatevere other name you use for the instance (without excplicity specigying the instance type) will run an instance of type 'standard'.

The **interactive** instance has the particularity tha it does not start supervisord, but it start a shell and gives you acces to in in the terminal.

The **safemode** instance is ain interactive instance but the entrypoint-local.sh script is not executed to allow debugging in cases where the instance cannot even start. (see more about the entrypoint-local.sh script in the dedicated section)

### Customizing container startup: the entrypoint-local.sh script
Coming soon...


### Building a project: the build.conf file
Coming soon...

### Running a project: the run.conf file
Coming soon...