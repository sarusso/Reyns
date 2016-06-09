
DockerOps
=========

Simple yet powerful Docker operations orchestrator for managing entire platforms. Allows to speed up both Dev (every developer can run its own instance of the platform) and Ops (what is put in production is deterministically tested before).

Developed By Stefano Alberto Russo with an important contribution from Gianfranco Gallizia. Thanks also to Enerlife (http://www.enerlife.it) and eXact Lab (http://www.exact-lab.it) for allowing this project to be open source.


&nbsp;
# Quick start and demo
---

**Dependencies:** Docker, Fabric (apt-get install fabric). Please note that Fabric requires Python version 2.5 - 2.7.

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
	- to see running services, type "dockerops ps"
	- to ssh into the "demo", instance "two" service, type "dockerops ssh:demo,instance=two"
	 - to ping service "demo", instance "one", type: "ping demo-one"
	 - to exit ssh type "exit"
	- to stop the demo, type "dockerops clean:all"


&nbsp;
# Documentation
---

## Introduction and basics

DockerOps allow you to manage a set of *services* (defined trought Docker images and run as Docker containers) by defining how to build, run and interconnect them in a *project*.

DockerOps comes with a base Docker image which you should build all your services, where Supervisor and SSH are installed and configured by default. The default user is named "dockerops" and it has the SSH keys for accessing every other service you create on top of the base image. Please note that in production you may want to change or remove the SSH keys.

A project is organized in folders: each service must have its own folder and by default they have to be contained in a top-level folder named "services". Inside the folder of a service, you have to place a Dockerfile wich starts with the line: 

	FROM dockerops/dockerops-base-ubuntu14.04
	
..and with your Dokerfile commands.

The basic usage of DockerOps relies on four very simple commands.

- First, you have to build your service using `dockerops build:your_service_name`.
- Then, you can run an instance of it by simply typing `dockerops run:your_service_name`. In this case a the name choosen for the instance is randomly generated.
-  Once the service is started, you can ssh into is using `dockerops ssh:your_service_name`.
-  To turn it off, just use `dockerops clean:your_service_name`.

## Building a service

To build a sevice you also have to actually sun some application in it. To do so the sugested way is to use Supervisord. The following Example is taken from DockerOps' internal DNS:

    [program:bind]
    
    ; Process definition
    process_name = bind
    command      = /runbind.sh
    autostart    = true
    autorestart  = true
    startsecs    = 5
    stopwaitsecs = 10
    priority     = 100

    ; Log files
    stdout_logfile          = /var/log/supervisor/%(program_name)s_out.log
    stdout_logfile_maxbytes = 100MB
    stdout_logfile_backups  = 5
    stderr_logfile          = /var/log/supervisor/%(program_name)s_err.log
    stderr_logfile_maxbytes = 100MB
    stderr_logfile_backups  = 5

..and this configuration file (which is named "supervisord_bind.conf") should be palces in supervisor/conf.d/. In your Dockerfile:

    COPY supervisord_bind.conf /etc/supervisor/conf.d/

This approach allows you also to hierarchically extend services. There is also support for executing custom entrypoins for each service, hierarchically:

    COPY entrypoint-dns.sh /entrypoints/
    RUN chmod 755 /entrypoints/entrypoint-dns.sh
    RUN mv /entrypoints/entrypoint-dns.sh /entrypoints/entrypoint-dns-$(date +%s).sh 

The DockerOps' entrypopint will execute every entrypoint inside the /entrypoints/ directory of the service, and with the above syntax it will execute parent's custom entrypoints first. It is highly suggested to always use this lines. In the service entrypoint you also have full access to all environment variables (read the "Environment variables" section for more details about them). 

## Runnign a service

As for the building, place yourself at the level of the apps_services directory, and issue the following command.


    dockerops run:your_service_name[,instance=your_instance_name, instance_type=standard
                  published/master, group=your_service_group_name, persistent_data=True/False,
                  persistent_log=True/False, persistent_opt=True/False, publish_ports=True/False,
                  linked=True/False, seed_command=cusom_seed_command, safemode=True/False,
                  interactive=True/False, debug=True/False, conf=conf_file(default:run.conf)]

All the above arguments are explained in detail in the following sections. There are also some env variables



## Services properties

When you run a service using DockerOps, there are a few properties already implemented to make the life easier. These are:

* `linked`: linking enabled or not (according to the project's run.conf, see later)
* `publish_ports`: if set to true, publish the ports on the host according to the EXPOSE instruction in the Dockerfile
* `persistent_data`: if enabled, all the data in /data inside the service is made persistent on the host filesystem (if data is already present, it is preserved) 
* `persistent_opt`: if enabled, all the data in /opt inside the serviceis made persistent on the host filesystem (if data is already present, it is preserved) 
* `persistent_log`: if enabled, all the data in /var/log inside the service is made persistent on the host filesystem (if data is already present, it is preserved) 


## Instances
DockerOps introduces the concept of *instances* of the same Docker conatiner: this is just a naming convention and does not modify in any way how Docker works, but it is an extremely useful feature. For examle you can have a service running in two instances (i.e. nodeA and nodeB)

A DockerOps instance can be of four *instance types*: **standard**, **published**, **master**, **interactive** and **safemode**. The safemode and interactive instances types will be covered more in detail in thei section. The following table summarize the defaults properies for the instances types, but no one prevents you from specifying custom settings (command line arguments have the highest possible precedence in DockerOps)

| Instance type | linked | publish ports | persistent data | persisten opt | persistent log | 
|---------------|:------:|:-------------:|:---------------:|:-------------:|---------------:|
| standard      | YES    | NO            | NO              | NO            | NO             |  
| published     | YES    | YES           | NO              | NO            | NO             |
| master        | YES*   | YES           | YES             | NO            | YES            |

*the linking in an instance of type **master** require a proper setting of the env vars (as explained in the dedicated section) or using the DNS service (dockerops-dns)

There is also a rapid shortcut when running the services: if you do not specify the instance type but you name an instance **master** or **published**, the instance type will be set accordingly. Whatevere other name you use for the instance (without excplicity specifying the instance type) will run an instance of type 'standard'.

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

An instance which run in  **interactive** mode has the particularity tha it does not start supervisord, but it start a shell and gives you acces to in in the terminal. In an instance which run in **safemode** the the entrypoints are not executed, to allow debugging in cases where the instance cannot even start. (see more about the entrypoint-local.sh script in the dedicated section)

You may also want to siable linking my specifing **linked=False** depending on the use case. You can also have an instance which runs both in safemode and interactively

Example:

    dockerops run:postgres,instance=one,safemode=True,interactive=True,linked=False


## Taking control of the services

### Environment variables
The resolution of the environment variables follow the priority order reported below:

1. Environment variable vars set at runtime
2. Environment variable specified in the host.conf file
3. Environment variable set int he run conf file being used (i.e. run.cof, or run_published.conf, or...)

The service has full visibiliy on a fixed set of environment varibales, which are:

**SERVICE_IP**: where the service(s) is expected to respond. In particular, the IP used to register the service on the Dynamic DNS, and the IP on which the DNS itself will respond. If not set, docker network IP addresses are used. Mandatory if the instance type is 'master'.

**SERVICE**: service name.

**INSTANCE**: instance name.

**INSTANCE_TYPE**: instance type.

**PERSISTENT_DATA**: if data is set to persisistent or not.

**PERSISTENT_LOG**: if log is set to persisistent or not.

**PERSISTENT_OPT**: if opt is set to persisistent or not.

**SAFEMODE**: if safemode is enabled or not.

**HOST_HOSTNAME**: Host's hostname.


*Note:* If a variable starts with "from_", then DockerOps will set the value using the IP of the network interface coming after. In example, "from_eth0" will take the value of the IP address of the host's eth0 network interface.

### Entrypoints
Coming soon...

## Project-level management
Concepts..
### Building a project
Coming soon...
### Running a project
Coming soon...

### Linking
DockerOps supports (and extends) standard style Docker's linking system, but only at project-level trought the run conf setings. Links have to be defined in the run conf file, and can be extended or simple. An extended link works as follows:

    "links": [
               {
                 "name": "MYAPP",
                 "service": "myapp_service",
                 "instance": null
                }
              ]

If this method is used, DockerOps set up a link with the linked service by providing an environment  variable named MYAPP_SERVICE_IP in the service linking the MYAPP service.

The above fields should be self-explanatory. The 'null' value in the instance means "Find any running instance of the service 'myapp_service'" and link against it. If more than one instances are found, the link against the first one and issue a warning. You can of course set a name in the instance filed, as 'master', 'one', or 'myinstance1'.

You can also set up quick and simple links by using the following syntax (with wildcards support):

    "links": ["dockerops-dns-master:dns"],

which correspond to the following syntax:

    "links": [
               {
                 "name": "dns",
                 "service": "dockerops-dns",
                 "instance": "master"
               }
             ]

The suggested way to link services is, anyway, to use DockerOps' Dynamic DNS (see section "DockerOps Dynamic DNS"). See the relevant sections for more informations about how to use the service. The pro of this approach is that you you can shut down and up any service independently and avoid to end up with a broken linking. 


## DockerOps' Dynamic DNS 

DockerOps provides a dynamic DNS service. If enabled, Other services running in the same project
updates their records so that you can interconnect services just by using the hostname. This method
is much more powerful that base Docker linking, as it allows to move a service on another host seamlessly.

To use it in your project, just add it to the `run.conf` file following this example:

    [
     {
      "service": "dockerops-dns",
      "instance": "master",
      "sleep": 0,
      "links": [],
      "env_vars": {"SERVICE_IP":"from_eth0" }
      },
     {
      "service": "dockerops-base",
      "instance": "one",
      "sleep": 0,
      "links": ["dockerops-dns-master:dns"],
      },
     {
      "service": "dockerops-base",
      "instance": "two",
      "sleep": 0,
      "links": [],
      "env_vars": {"DNS_SERVICE_IP": "from_eth0" }
       },
      {
      "service": "demo",
      "instance": "one",
      "sleep": 0,
      "links": [
                 {
                   "name": "BASE",
                   "service": "dockerops-base",
                   "instance": null
                  }
                ]
      }
     ]

You can see this example in action by just typing 'dockerops install_demo' and following the quickstart.

After this, you should be able to contact the DNS service and ask it your local zone members (e.g. via `host dns.local.zone.`).

Note that for enabling the DNS service the connection can both be established using the standard linking and just by setting the DNS_SERVICE_IP env var.

Services can register themselves to the DNS using three approaches, defined trought the environment variable DNS_UPDATE_POLICY:

- **DNS_UPDATE_POLICY="HIDED"**: In this case the service is not published to the DNS, but the DNS service is queryable. Useful for testing purposes.

- **DNS_UPDATE_POLICY="APPEND"** (default): In this case the DNS record corresponding to the service name is appended, so if there is another service wiht the same name running (but different instance) and you query the DNS for the service name, both the IPs of the services will be provided (in round robin). Particluary useful for scaling up.

- **DNS_UPDATE_POLICY="UPDATE"**: In this case the DNS record corresponding to the service name, if already present, is replaced. So, if there is another service wiht the same name running (but different instance) and you query the DNS for the service name, only the last run service IP address will be provided. Usefoul for hot-updating servers.

Notes:

Be sure that nothing is listening on port 53 both TCP **AND** UDP (E.G.
dnsmasq or bind) on **your** host because DNS queries are sent through
UDP but DNS updates are sent through TCP so both need to be available.

Also please note that you might want to increase the sleep timer to allow
bind to set up in the DNS service.

Thanks to Gianfranco Gallizia and eXact Lab (http://www.exact-lab.it/) for this contribution.


## Logging and debugging

To enable the debug mode, just set the "LOG_LEVEL" env var to "DEBUG". for example:

    LOG_LEVEL=DEBUG dockerops run:postgres,instance=master
    
If you insance does not run as expect when starting (and since it does not start you cannot ssh in it) you can try few things:

First of all, you can try to run in in an interactive way:
    
    dockerops run:postgres,instance=master,interactive=True,safemode=True

This will run DokcerOps's entrypoint, the services aentrypoints and give you a shell. You can then type 'supervisord' to start the service as normal (but still interactivey).

If you have errors in the execution of the entrypoint of some services, you can use the safemode, which just run  DokcerOps's entrypoint (that should never fail) and not the service entrypoints (the scripts in the directory '/entrypoints'). 

    dockerops run:postgres,instance=master,safemode=True

..or you can cobine the two.

    dockerops run:postgres,instance=master,interactive=True,safemode=True

If you still have errors, and in partiucular you are running with persistent data enabled, then you can try to rename the data dir temporary (to understande the mv: inter-device move failed error, in particular).


Licensing
=========
DockerOps is licensed under the Apache License, Version 2.0. See
[LICENSE](https://raw.githubusercontent.com/sarusso/DockerOps/master/LICENSE) for the full
license text.






