
Reyns
=====

Simple yet powerful local (micro) services orchestrator capable of managing entire platforms. Allows to speed up both Dev (every developer can run its own instance of the platform) and Ops (what is put in production is deterministically tested before).

Developed by Stefano Alberto Russo with an important contribution from Gianfranco Gallizia. Thanks also to Enerlife (http://www.enerlife.it) and eXact Lab (http://www.exact-lab.it) for allowing this project to be open source.


# Quick start and demo

**Requirements:** Docker > 1.9.0, Bash, Python 2.7 to 3.6.

To install, run the following commands:

	$ git clone https://github.com/sarusso/Reyns.git
	$ cd Reyns
	$ ./install.sh

To install and run the demo, run the following commands:

	$ reyns install_demo
	Demo installed.
	Quickstart: enter into "reyns-demo", then:
	- to build it, type "reyns build:all"
	- to run it, type "reyns run:all"
	- to see running services, type "reyns ps"
	- to ssh into the "demo", instance "two" service, type "reyns ssh:demo,instance=two"
	 - to ping service "demo", instance "one", type: "ping demo-one"
	 - to exit ssh type "exit"
	- to stop the demo, type "reyns clean:all"


# Documentation

## Introduction and basics

Reyns allow you to manage a set of *services* (defined through Docker images and run as Docker containers) by defining how to build, run and interconnect them in a *project*.

Reyns comes with a base Docker image which you should build all your services, where Supervisor and SSH are installed and configured by default. The default user is named "reyns" and it has the SSH keys for accessing every other service you create on top of the base image. Please note that in production you may want to change the SSH keys and/or the rndc (DNS) key in the "keys" folder.

A project is organised in folders: each service must have its own folder and by default they have to be contained in a top-level folder named "services". Inside the folder of a service, you have to place a Dockerfile which starts with the line: 

	FROM reyns/reyns-base-ubuntu14.04
	
..and with your Dokerfile commands.

The basic usage of Reyns relies on four very simple commands.

- First, you have to build your service using `reyns build:your_service_name`.
- Then, you can run an instance of it by simply typing `reyns run:your_service_name`. In this case a the name chosen for the instance is randomly generated.
-  Once the service is started, you can ssh into is using `reyns ssh:your_service_name`.
-  To turn it off, just use `reyns clean:your_service_name`.

## Building a service

The first thing you probably want to do in your services is to run some applications (or daemons). The suggested way is to use Supervisord. The following Example is taken from Reyns' internal DNS:

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

..and this configuration file (which is named "supervisord_bind.conf") should be placed in supervisor/conf.d/. In your Dockerfile:

    COPY supervisord_bind.conf /etc/supervisor/conf.d/

This approach allows you also to hierarchically extend services. There is also support for executing custom prestartup scripts for each service, hierarchically:

    COPY prestartup_reyns--dns.sh /prestartup/

The Reyns' entrypoint script will execute every script inside the /prestartup/ directory of the service, and it will execute parent's prestartup scripts first. In the service prestartup scripts you also have full access to all environment variables (read the "Environment variables" section for more details about them). 

## Running a service

As for the building, place yourself at the level of the apps_services directory, and issue the following command.


    $ reyns run:your_service_name[,instance=your_instance_name, instance_type=standard
                  published/persistent/master/debug, group=your_service_group_name, persistent_data=True/False,
                  persistent_opt=True/False, persistent_log=True/False, publish_ports=True/False,
                  linked=True/False, seed_command=custom_seed_command, safemode=True/False,
                  interactive=True/False, conf=conf_file(default:default.conf)]

All the above arguments are explained in detail in the following sections. There are also some env variables



## Services properties

When you run a service using Reyns, there are a few properties already implemented to make the life easier. These are:

* `persistent_data`: if enabled, all the data in /data inside the service is made persistent on the host filesystem (if data is already present, it is preserved).
* `persistent_opt`: if enabled, all the data in /opt inside the services made persistent on the host filesystem (if data is already present, it is preserved).
* `persistent_log`: if enabled, all the data in /var/log inside the service is made persistent on the host filesystem (if data is already present, it is preserved).
* `publish_ports`: if set to true, publish the ports on the host according to Reyns comment-annotations in the Dockerfile (i.e. "# reyns: expose 53/tcp" or "# reyns: expose 53/udp").
* `linked`: linking enabled or not (according to the conf file being used, see later).
* `seed_command`: specify here a custom seed command to execute at the service startup. The default is 'supervisord'.
* `safemode`: if enabled services prestartup scripts will not be executed. See the "Logging and debugging" section for more info.
* `interactive`: provides you an interactive shell. See the "Logging and debugging" section for more info.
* `conf`: the configuration file to use (with or without the ".conf" extension).


## Instances
Reyns introduces the concept of *instances* of the same Docker container (or Reyns service): this is just a naming convention and does not modify in any way how Docker works, but it is an useful logical separation. For example you can have a service running in two instances (i.e. nodeA and nodeB).

A Reyns instance can be of five `instance_type `: **standard**, **published**, **persistent**, **master** and **debug**. The following table summarize the default propertied for the instances types, but no one prevents you from specifying custom settings (command line arguments have the highest possible priority in Reyns)

| Instance name | Intance type| linked | publish ports | persistent data | persisten opt | persistent log | interactive | prestartup executed| 
|---------------|-------------|:------:|:-------------:|:---------------:|:-------------:|:--------------:|:-----------:|:------------------:|
| &nbsp; *      | standard    | YES    | NO            | NO              | NO            | NO             | NO          | YES                |
| published     | published   | YES    | YES           | NO              | NO            | NO             | NO          | YES                |
| persistent    | persistent  | YES    | NO            | YES             | NO            | YES            | NO          | YES                |
| master        | master      | YES*   | YES           | YES             | NO            | YES            | NO          | YES                |
| debug         | debug       | NO     | NO            | NO              | NO            | NO             | YES         | NO                 |


*the linking in an instance of type **master** without using the DNS service (reyns-dns) requires a proper setting of the environment 
variables (as explained in the dedicated section "Linking")

*Note:* basically, a master instance is a instance of both types published and persistent.

Examples for running a standard instance:

    $ reyns run:postgres,instance=one
    $ reyns run:postgres,instance=master,instance_type=standard

Examples for running a published instance:

    $ reyns run:postgres,instance=published
    $ reyns run:postgres,instance=one,instance_type=published

Examples for runnign a master instance:

    $ reyns run:postgres,instance=master
    $ reyns run:postgres,instance=one,instance_type=master
    

There are also two particular ways of running instances of a given type: *interactive* and in *safe mode*.

An instance which run in  **interactive** mode has the particularity that it does not start supervisord, but it start a shell and gives you access to in in the terminal. In an instance which run in **safemode** the the prestartup scripts are not executed, to allow debugging in cases where the instance cannot even start.

You may also want to disable linking by using **linked=False** depending on the use case. You can also have an instance which runs both in safemode and interactively

Example:

    $ reyns run:postgres,instance=one,safemode=True,interactive=True,linked=False


## Taking control of the services

### Environment variables
The resolution of the environment variables follow the priority order reported below:

1. Environment variable vars set at runtime
2. Environment variable specified in the host.conf file
3. Environment variable set int he run conf file being used (i.e. run.cof, or run_published.conf, or...)

The service has full visibility on a fixed set of environment variables, which are:

**SERVICE_IP**: where the service(s) is expected to respond. In particular, the IP used to register the service on the Dynamic DNS, and the IP on which the DNS itself will respond. If not set, docker network IP addresses are used. Mandatory if the instance type is 'master'.

**SERVICE**: service name.

**INSTANCE**: instance name.

**INSTANCE_TYPE**: instance type.

**PERSISTENT_DATA**: if data is set to persisistent or not.

**PERSISTENT_LOG**: if log is set to persisistent or not.

**PERSISTENT_OPT**: if opt is set to persisistent or not.

**SAFEMODE**: if safemode is enabled or not.

**HOST_HOSTNAME**: Host's hostname.


*Note:* If a variable starts with "from_", then Reyns will set the value using the IP of the network interface coming after. In example, "from_eth0" will take the value of the IP address of the host's eth0 network interface.

### Prestartup scripts
Coming soon...

## Project-level management
Concepts..
### Building a project
Coming soon...
### Running a project
Coming soon...

### Linking
**Linking is going to be deprecated in Docker soon**. Reyns supports (and extends) standard style Docker's linking system, but only at project-level thought the run conf settings. Links have to be defined in the run conf file, and can be extended or simple. An extended link works as follows:

    "links": [
               {
                 "name": "MYAPP",
                 "service": "myapp_service",
                 "instance": null
                }
              ]

If this method is used, Reyns set up a link with the linked service by providing an environment  variable named MYAPP_SERVICE_IP in the service linking the MYAPP service.

The above fields should be self-explanatory. The 'null' value in the instance means "Find any running instance of the service 'myapp_service'" and link against it. If more than one instances are found, the link against the first one and issue a warning. You can of course set a name in the instance filed, as 'master', 'one', or 'myinstance1'.

You can also set up quick and simple links by using the following syntax (with wildcards support):

    "links": ["reyns-dns-master:dns"],

which correspond to the following syntax:

    "links": [
               {
                 "name": "dns",
                 "service": "reyns-dns",
                 "instance": "master"
               }
             ]

The suggested way to link services is, anyway, to use Reyns' Dynamic DNS (see section "Reyns Dynamic DNS"). See the relevant sections for more informations about how to use the service. The pro of this approach is that you you can shut down and up any service independently and avoid to end up with a broken linking. 


## Reyns' Dynamic DNS 

Reyns provides a dynamic DNS service. If enabled, Other services running in the same project
updates their records so that you can interconnect services just by using the hostname. This method
is much more powerful that base Docker linking, as it allows to move a service on another host seamlessly.

To use it in your project, just add it to the conf file following this example:

    [
     {
      "service": "reyns-dns",
      "instance": "master",
      "sleep": 0,
      "links": [],
      "env_vars": {"SERVICE_IP":"from_eth0" }
      },
     {
      "service": "reyns-base",
      "instance": "one",
      "sleep": 0,
      "links": ["reyns-dns-master:dns"],
      },
     {
      "service": "reyns-base",
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
                   "service": "reyns-base",
                   "instance": null
                  }
                ]
      }
     ]

You can see this example in action by just typing 'reyns install_demo' and following the quickstart.

After this, you should be able to contact the DNS service and ask it your local zone members (e.g. via `host dns.local.zone.`).

Note that for enabling the DNS service the connection can both be established using the standard linking and just by setting the DNS_SERVICE_IP env var.

Services register themselves on the DNS both as their hostname (i.e. "demo-one") and as their service name (i.e. "demo"). The behaviour on how to handle the service name (i.e. "demo") in case of multiple instances (i.e. "demo-one" and "demo-two") depends on the update policy, which is defined thought the environment variable DNS_UPDATE_POLICY and can follow three different approaches:

- **DNS_UPDATE_POLICY="HIDE"**: The service is not published to the DNS at all, but the DNS service is queryable. Useful for testing purposes as an "observer".

- **DNS_UPDATE_POLICY="REPLACE"** *(default)*: the DNS record corresponding to the service name, if already present, is replaced. In other words, if there are two instances of the same service running and you query the DNS for the service name, only the IP address of the last instance will be provided. Useful for hot-updating servers.

- **DNS_UPDATE_POLICY="APPEND"**: In this case the DNS record corresponding to the service name is appended, so if there are two instances of the same service running and you query the DNS for the service name, both the IPs of the instances will be provided (in Round Robin). Particularly useful for scaling up. Please note that scaling down and re-running services is not supported for now, as removing records from the DNS is not yet supported.


**Notes:**

If running in published mode, be sure that nothing is listening on port 53 both TCP **AND** UDP (E.G.
dnsmasq or bind) on **your** host because DNS queries are sent through
UDP but DNS updates are sent through TCP so both need to be available.

Also, you might want to increase the sleep timer to allow bind to set up in the DNS service.

Thanks to Gianfranco Gallizia and eXact Lab (http://www.exact-lab.it/) for this contribution.


## Multi-node setup
While not one of its core features, Reyns support to deploy project across multiple nodes. This requires publishing all necessary ports for inter-node communications as well as the DNS service. please not that this setup is suited for private networks _only_. Never publish Reyns' dynamic DNS on a public IP.

To configure a multi-node setup, you can start from the demo, using the "default-multinode.conf" file as a guide. To test on a single node before going multi-node, just install the demo somewhere (with "reyns install_demo") but instead of following the quick start run the following commands:

    $ reyns run:group=master,conf=default-multinode
    $ reyns run:group=node1,conf=default-multinode
    $ reyns run:group=node2,conf=default-multinode

You will be asked for the DNS_SERVICE_IP env var: here you need to put the external IP address of the external network interface.

Test with:

    $ reyns ssh:demo,onenode2
    reyns@demo-onenode2:~$ ping demo-onenode1

**Note:** the  "default-multinode.conf" file shipped with the demo assume the network interface "eth0" as the external interface (the "from_eth0" placeholder). You can change (i..e on en0 for macOS) or just replace it with the external IP address instead of the "" 
 

## Logging and debugging

To enable the debug mode, just set the "LOG_LEVEL" env var to "DEBUG". for example:

    $ LOG_LEVEL=DEBUG reyns run:postgres,instance=master
    
If you instance does not run as expect when starting (and since it does not start you cannot ssh in it) you can try few things:

First of all, you can try to run in in an interactive way:
    
    $ reyns run:postgres,instance=master,interactive=True

This will run the services prestartup scripts and and give you a shell. You can then type 'supervisord' to start the service as normal (but still interactively).

If you have errors in the execution of the prestartup scripts for some services, you can use the safemode, which just runs  Reyns's prestartup (that should never fail) and not the service prestarup scripts

    $ reyns run:postgres,instance=master,safemode=True
        

You can also combine the two, which is probably the most useful approach:

    $ reyns run:postgres,instance=master,interactive=True,safemode=True

..and you can execute the prestartup scripts in the interactive mode just by typing /prestartup.sh.        

Note: Sometimes you can get an error similar to "mv: inter-device move failed error". In this case, and in partiucular if you are running with persistent data enabled,  you can try to temporary rename the data dir to understand why the error arise.


## Troubleshooting
In case of a failure in the building process: first of all, retry building (maybe temporary network problem). If error persist, try building without cache (i.e. reyns build:all,cache=False), fis till no errors, try to re-init base containers (reyns init). Also check disk space both on local filesystem and in the virtual machine filesystem if on Windows or Mac.

# Licensing
Reyns is licensed under the Apache License, Version 2.0. See
[LICENSE](https://raw.githubusercontent.com/sarusso/Reyns/master/LICENSE) for the full
license text.






