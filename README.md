**WARNING: this is beta software under heavy development.**  

If you are interested in contributing please drop me a line at stefano.russo@gmail.com.


DockerOps
=========


Simple yet powerful Docker operations orchestrator for managing entire platforms. Allows to speed up both Dev (every developer can run its own instance of the platform) and Ops (what is put in production is deterministically tested before). 

# Prerequisites

Docker, Fabric (apt-get install fabric)


# Quick start and demo

To install, run the following commands:

	# git clone https://github.com/sarusso/DockerOps.git
	# cd DockerOps
	# ./install.sh (Several minutes needs to fetch Ubuntu base image )

To install and run the demo, run the following commands:

	# mkdir $HOME/Demo-DockerOps
	# cd $HOME/Demo-DockerOps
	# dockerops install_demo
	Demo installed.
	Quickstart: enter into $HOME/Demo-DockerOps, then:
	- to build it, type "dockerops build:all"
	- to run it, type "dockerops run:all"
	- to see running containers, type "dockerops ps"
	- to ssh into the "dockerops-base", instance "two" container, type "dockerops ssh:dockerops-base,instance=one"
	 - to ping container "dockerops-base", instance "two", type: "ping dockerops-base-two"
	 - to exit ssh type "exit"
	- to stop the demo, type "dockerops clean:all"


# Documentation


## Introduction and basics

DockerOps allows you to define how to build, run and interconnect a set (or from now on, a *project*) of Docker containers. It comes with a base container on which you should build all your Dockers, where Supervisor and SSH are installed and configured by default. The base container has a default user named "dockerops" which has the SSH keys for accessing every Docker container you create on top of the base container. Please not that in production you may want to change or remove the SSH keys.

A project is organized in folders: each Docker container must have its own folder and by default they have to be contained in a folder named "apps_containers". Inside the folder of a container, you have to place a Dockerfile wich starts with the line: 

	FROM your_project_name/dockerops-base

The basic usage relise on four very simple commands. Fisrt you have to build your container using `dockerops build:your_container_name`, then you can run it by simply typing `dockerops run:your_container_name`. Once the container is started, you can ssh into is using `dockerops ssh:your_container_name`, and turn it off using dockerops `clean:your_container_name`.

## Building a container

Place yourself in a  directoy and create a subdir named apps_containers. Then create a subdir of apps_containers named your_container_name. here, create a file named Dockerfile where to put your Docker build commands. Remember to always extend the dockerops-base container (`FROM your_project_name/dockerops-base`) in the Dockerfile

Now, place yourself at the level of the apps_containers directory, and issue the following command.

    dockerops build:your_container_name[,verbose]

## Runnign a container

As for the building, place yourself at the level of the apps_containers directory, and issue the following command.


    dockerops run:your_container_name[,instance=your_instance_name, instance_type=standard
                  published/master, group=your_container_group_name, persistent_data=True/False,
                  persistent_log=True/False, persistent_opt=True/False, publish_ports=True/False,
                  linked=True/False, seed_command=cusom_seed_command, safemode=True/False,
                  interactive=True/False, debug=True/False, conf=conf_file(default:run.conf)]

All the above arguments are explained in detail in the following sections.


## Containers properties

When you run a Docker container using DockerOps, there are a few properties already implemented to make the life easier. These are:

* `linked`: linking enabled or not (according to the project's run.conf, see later)
* `publish_ports`: if set to true, publish the ports on the host according to the EXPOSE instruction in the Dockerfile
* `persistent_data`: if enabled, all the data in /data inside the container is made persistent on the host filesystem (if data is already present, it is preserved) 
* `persistent_opt`: if enabled, all the data in /opt inside the containeris made persistent on the host filesystem (if data is already present, it is preserved) 
* `persistent_log`: if enabled, all the data in /var/log inside the container is made persistent on the host filesystem (if data is already present, it is preserved) 


## Instances
DockerOps introduces the concept of *instances* of the same Docker conatiner: this is just a naming convention and does not modify in any way how Docker works, but it is an extremely useful feature. For examle you can have a container running in two instances (i.e. nodeA and nodeB)

A DockerOps instance can be of four *instance types*: **standard**, **published**, **master**, **interactive** and **safemode**. The safemode and interactive instances types will be covered more in detail in thei section. The following table summarize the defaults properies for the instances types, but no one prevents you from specifying custom settings (command line arguments have the highest possible precedence in DockerOps)

| Instance type | linked | publish ports | persistent data | persisten opt | persistent log | 
|---------------|:------:|:-------------:|:---------------:|:-------------:|---------------:|
| standard      | YES    | NO            | NO              | NO            | NO             |  
| published     | YES    | YES           | NO              | NO            | NO             |
| master        | YES*   | YES           | YES             | NO            | YES            |

*the linking in an instance of type **master** require a proper setting of the env vars (as explained in the dedicated section) or using the DNS service (dockerops-dns)

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


## Customizing container startup
### The entrypoints
Coming soon...

## Building a project
### Concepts
Coming soon...
### The build.conf file
Coming soon...


## Running a project
### Concepts
Coming soon...

### The Linking
DockerOps provides an extended system for linging containers. There are three main ways:

1) Explicit links (with wildcards supports)
This class set up a link with the linked container providing an env var named MYAPP_CONTAINER_IP in the container linking the MYAPP container. Explit links are definred in the run.conf file, and can be extended or simple. An extended lik works as follows:

      "links": [
                 {
                   "name": "MYAPP",
                   "container": "myapp_container",
                   "instance": null
                  }
                ]

The fields should be self-explanatory. The 'null' value in the instance means "Find any running instance of the container 'myapp_containe'" and link against it. If more than one instances are found, the link against the first one and issue a warning. You can of course set a name in the instance filed, as 'master', 'one', or 'myinstance1'.

You can also set up quick and simple links by using the following syntax:

    "links": ["dockerops-dns-master:dns"],

which correspond to the following syntax:

      "links": [
                 {
                   "name": "dns",
                   "container": "dockerops-dns",
                   "instance": "master"
                  }
                ]


2) DNS links

Another way of reating links is by using the DockerOps Dynamic DNS. See the relevant sections for more informations about how to use the service. The pro of this approach is that you you can shut down and up any container independently and avoid to end up with a broken linking. The cons is that you must fix instances names (as the name of the container 'myapp', instance 'one' is myapp-one) so you should pay more attention in assigning names to the instances. Please note that to set a instance in 'master' or 'published' mode, instead of changing the name, you can just set the 'master' or 'published' flag in the run.conf.  


### The run.conf file
Coming soon...


## DockerOps Dynamic DNS 

DockerOps provides a dynamic DNS container. If enabled, Other containers running in the same project
updates their records so that you can interconnect containers just by using the hostname. This method
is much more powerful that base Docker linking, as it allows to move a container on another host seamlessly.

To use it in your project, just add it to the `run.conf` file following this example:

    [
     {
      "container": "dockerops-dns",
      "instance": "master",
      "sleep": 0,
      "links": [],
      "env_vars": {"HOST_FQDN": null, "HOST_IP":"from_eth0" }
      },
     {
      "container": "dockerops-base",
      "instance": "one",
      "sleep": 0,
      "links": ["dockerops-dns-master:dns"],
      "env_vars": {"HOST_FQDN": null}
      },
     {
      "container": "dockerops-base",
      "instance": "two",
      "sleep": 0,
      "links": [],
      "env_vars": {"HOST_FQDN": null, "DNS_CONTAINER_IP": "from_eth0" }
       },
      {
      "container": "demo",
      "instance": "one",
      "sleep": 0,
      "links": [
                 {
                   "name": "BASE",
                   "container": "dockerops-base",
                   "instance": null
                  }
                ]
      }
     ]

You can see this example in action by just typing 'dockerops install_demo' and following the quickstart.

After this, you should be able to contact the DNS container
and ask it your local zone members (e.g. via `host dns.local.zone.`).

Notes:

Be sure that nothing is listening on port 53 both TCP **AND** UDP (E.G.
dnsmasq or bind) on **your** host because DNS queries are sent through
UDP but DNS updates are sent through TCP so both need to be available.

Also please note that you might want to increase the sleep timer to allow
bind to set up in the DNS container.

Thanks to Gianfranco Gallizia and eXat Lab (http://www.exact-lab.it/) for this contribution.


## Logging and debugging

To enable the debug mode, just set the "LOG_LEVEL" env var to "DEBUG". for example:

    LOG_LEVEL=DEBUG dockerops run:postgres,instance=master
    
If you insance does not run as expect when starting (and since it does not start you cannot ssh in it) you can try few things:

First of all, you can try to run in in an interactive way:
    
    dockerops run:postgres,,instance=master,interactive=True,safemode=True

This will run DokcerOps's entrypoint, the containers aentrypoints and give you a shell. You can then type 'supervisord' to start the container as normal (but still interactivey).

If you have errors in the execution of the entrypoint of some containers, you can use the safemode, which just run  DokcerOps's entrypoint (that should never fail) and not the container entrypoints (the scripts in the directory '/entrypoints'). 

    dockerops run:postgres,,instance=master,safemode=True

..or you can cobine the two.

    dockerops run:postgres,,instance=master,interactive=True,safemode=True

If you still have errors, and in partiucular you are running with persistent data enabled, then you can try to rename the data dir temporary (to understande the mv: inter-device move failed error, in particular).


Licensing
=========
DockerOps is licensed under the Apache License, Version 2.0. See
[LICENSE](https://raw.githubusercontent.com/sarusso/DockerOps/master/LICENSE) for the full
license text.






