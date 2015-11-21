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

The basic usage relise on four very simple commands. Fisrt you have to build your container using `dockerops build:your_container_name`, then you can run it by simply typing `dockerops run:your_container_name`. Once the container is started, you can ssh into is using `dockerops ssh:your_container_name`, and turn it off using dockerops `clean:your_container_name`.

### Building a container

Place yourself in a  directoy and create a subdir named apps_containers. Then create a subdir of apps_containers named your_container_name. here, create a file named Dockerfile where to put your Docker build commands. Remember to always extend the dockerops-base container (`FROM your_project_name/dockerops-base`) in the Dockerfile

Now, place yourself at the level of the apps_containers directory, and issue the following command.

    dockerops build:your_container_name[,verbose]

### Runnign a container

As for the building, place yourself at the level of the apps_containers directory, and issue the following command.


    dockerops run:your_container_name[,instance=your_instance_name, instance_type=standard/published/master, group=your_container_group_name, persistent_data=True/False, persistent_log=True/False, persistent_opt=True/False, publish_ports=True/False, linked=True/False, seed_command=cusom_seed_command, safemode=True/False,  interactive=True/False, debug=True/False, conf=conf_file(default:run.conf)]

All the above arguments are explained in detail in the following sections.


### Containers properties

When you run a Docker container using DockerOps, there are a few properties already implemented to make the life easier. These are:

* `linked`: linking enabled or not (according to the project's run.conf, see later)
* `publish_ports`: if set to true, publish the ports on the host according to the EXPOSE instruction in the Dockerfile
* `persistent_data`: if enabled, all the data in /data inside the container is made persistent on the host filesystem (if data is already present, it is preserved) 
* `persistent_opt`: if enabled, all the data in /opt inside the containeris made persistent on the host filesystem (if data is already present, it is preserved) 
* `persistent_log`: if enabled, all the data in /var/log inside the container is made persistent on the host filesystem (if data is already present, it is preserved) 


### Instances
DockerOps introduces the concept of *instances* of the same Docker conatiner: this is just a naming convention and does not modify in any way how Docker works, but it is an extremely useful feature. For examle you can have a container running in two instances (i.e. nodeA and nodeB)

A DockerOps instance can be of four *instance types*: **standard**, **published**, **master**, **interactive** and **safemode**. The safemode and interactive instances types will be covered more in detail in thei section. The following table summarize the defaults properies for the instances types, but no one prevents you from specifying custom settings (command line arguments have the highest possible precedence in DockerOps)

| Instance type | linked | publish ports | persistent data | persisten opt | persistent log | 
|---------------|:------:|:-------------:|:---------------:|:-------------:|---------------:|
| standard      | YES    | NO            | NO              | NO            | YES            |  
| published     | YES    | YES           | NO              | NO            | NO             |
| master        | YES*   | YES           | YES             | NO            | NO             |

*the linking in an instance of type **master** require a proper setting of the env vars, as explained in the dedicated section.

There is also a rapid shortcut when running the containers: if you do not specify the instance type but you name an instance **master** or **published**, the instance type will be set accordingly. Whatevere other name you use for the instance (without excplicity specifying the instance type) will run an instance of type 'standard'.

Examples for running a standard instance:

    dockerops run:postgres,instance=one
    dockerops run:postgres,instance=master,instance_type=standard

Examples for running a published instance:

    dockerops run:postgres,instance=published
    dockerops run:postgres,instance=one,instance_type=published

Examples for runnign a master instance:

	dockerops run:postgres,instance=master
    dockerops run:postgres,instance=one,instance_type=master
    

There are also two particular ways of running instances of a given type: *interactive* and in *safe mode*.

An instance which run in  **interactive** mode has the particularity tha it does not start supervisord, but it start a shell and gives you acces to in in the terminal. In an instance which run in **safemode** the entrypoint-local.sh script is not executed to allow debugging in cases where the instance cannot even start. (see more about the entrypoint-local.sh script in the dedicated section)

You may also want to siable linking my specifing **linked=False** depending on the use case. You can also have an instance which runs both in safemode and interactively

Example:

    dockerops run:postgres,instance=one,safemode=True,interactive=True,linked=False

### Customizing container startup: the entrypoint-local.sh script
Coming soon...

### Building a project: the build.conf file
Coming soon...

### Running a project: the run.conf file
Coming soon...

### Debugging

To enable the debug mode, just set the "LOG_LEVEL" env var to "DEBUG". for example:

    LOG_LEVEL=DEBUG dockerops run:postgres,instance=master








