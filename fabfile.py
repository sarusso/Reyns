#--------------------------
# Imports
#--------------------------

import os
import inspect
import uuid
import logging
import json
import socket

from fabric.utils import abort
from fabric.operations import local
from fabric.api import task
from fabric.contrib.console import confirm
from subprocess import Popen, PIPE
from collections import namedtuple

# TODO: Check taht we are in teh directory of the fab and not in one of its subfolders, abort in case

#--------------------------
# Conf
#--------------------------

DATA_DIR            = os.getenv('DATA_DIR', '/data/docker_data')
MY_CONTAINERS_DIR   = os.getenv('MY_CONTAINERS_DIR', 'my_containers')
BASE_CONTAINERS_DIR = os.getenv('BASE_CONTAINERS_DIR', 'base_containers')
LOG_LEVEL           = os.getenv('LOG_LEVEL', 'INFO')

# Defaults   
defaults={}
defaults['master']   = {'linked':False, 'persistent_data':True,  'persistent_opt': False, 'persistent_log':True,  'expose_ports':True,  'safemode':False}
defaults['safemode'] = {'linked':False, 'persistent_data':False, 'persistent_opt': False, 'persistent_log':False, 'expose_ports':False, 'safemode':True}
defaults['exposed']  = {'linked':True,  'persistent_data':False, 'persistent_opt': False, 'persistent_log':False, 'expose_ports':True,  'safemode':False}
defaults['standard'] = {'linked':True, 'persistent_data':False, 'persistent_opt': False, 'persistent_log':False, 'expose_ports':True,  'safemode':False}


#--------------------------
# Logger
#--------------------------

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s: %(message)s')
#logger = logging.getLogger(__name__)
logger = logging.getLogger('DockerOps')
logger.setLevel(getattr(logging, LOG_LEVEL))



#--------------------------
# Utility functions
#--------------------------

def sanity_checks(container, instance=None):
    
    caller = inspect.stack()[1][3]
    clean = True if 'clean' in caller else False
    build = True if 'build' in caller else False
    run   = True if 'run' in caller else False
    ssh   = True if 'ssh' in caller else False
    ip    = True if 'ip' in caller else False
    
    if not clean and not build and not run and not ssh and not ip:
        raise Exception('Unknown caller (got "{}")'.format(caller))

    # Check container name 
    if not container:
        if clean:
            abort('You must provide the container name or use the magic words "all" or "wide"') 
        else:
            abort('You must provide the container name or use the magic word "all"')
    
    # Check instance name     
    if not instance:
        
        if run:
            instance = str(uuid.uuid4())[0:8]
            
        if ssh or (clean and not container in ['all', 'wide']) or ip:
            running_instances = get_running_instances_matching(container)         
            if len(running_instances) == 0:
                abort('Could not find any running instance of container "{}"'.format(container))                
            if len(running_instances) > 1:
                logger.info('Found more than one running instance for container "{}": {}, using the first one ("{}")..'.format(container, running_instances, running_instances[0]))            
            instance = running_instances[0]
        
    if instance and build:
        abort('The build command does not make sense with an instance name (got "{}")'.format(instance))
    
    
    # Avoid 'wide' name if building'
    if build and container == 'wide':
        abort('Sorry, you cannot use the word "wide" as a container name as it is reserverd.')
    
    # Check container source if build:
    if build and container != 'all':
        container_dir = get_container_dir(container)
        if not os.path.exists(container_dir):
            abort('This container ("{}") does not have a source directory. I was looking for "{}".'.format(container, container_dir))
            
    return (container, instance)


def get_running_instances_matching(container):
    running =  ps(container=container, capture=True)
    instances = []
    if running:
        
        # TODO: Again, ps with capture on returns a list but shoudl return a dict.
        for container in running:
            fullname = container[-1]

            if ',instance=' in fullname:
                instances.append(fullname.split('=')[1])
            elif '-' in fullname:
                instances.append(fullname.split('-')[1])
            else:
                logger.warnign('Got inkinw name format from ps: "{}".format(fullname)')
               
            
    return instances


def get_container_dir(container=None):
    #logger.debug('Requested container dir for container %s', container )
    if container == 'base':
        return BASE_CONTAINERS_DIR + '/' + container
    else:
        return MY_CONTAINERS_DIR + '/' + container



def shell(command, capture=False, progress=False, interactive=False, silent=False):
    '''Execute a command in the shell. By defualt prints everything. If the capture switch is set,
    then it returns a namedtuple with stdout, stderr, and exit code.'''
    
    if capture and progress:
        raise Exception('You cannot ask at the same time for capture and progress, sorry')
    
    # If progress or interactive requested, just use fab's local
    if progress or interactive:
        return local(command)
    
    # Log command
    logger.debug('Shell executing command: "%s"', command)
    
    # Execute command getting stdout and stderr
    # http://www.saltycrane.com/blog/2008/09/how-get-stdout-and-stderr-using-python-subprocess-module/
    
    process          = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
    (stdout, stderr) = process.communicate()
    exit_code        = process.wait()

    # Formatting..
    stdout = stdout[:-1] if (stdout and stdout[-1] == '\n') else stdout
    stderr = stderr[:-1] if (stderr and stderr[-1] == '\n') else stderr

    # Output namedtuple
    Output = namedtuple('Output', 'stdout stderr exit_code')

    if exit_code != 0:
        if capture:
            return Output(stdout, stderr, exit_code)
        else:
            print format_shell_error(stdout, stderr, exit_code)           
            return False    
    else:
        if capture:
            return Output(stdout, stderr, exit_code)
        elif not silent:
            # Just print stdout and stderr cleanly
            print stdout
            print stderr
            return True
        else:
            return True
            
def booleanize(*args, **kwargs):
    # Handle both single value and kwargs to get arg name
    name = None
    if args and not kwargs:
        value=args[0]
    elif kwargs and not args:
        for item in kwargs:
            name  = item
            value = kwargs[item]
            break
    else:
        raise Exception('Internal Error')
    
    # Handle shortcut: an arg with its name equal to ist value is considered as True
    if name==value:
        return True
    
    if isinstance(value, bool):
        return value
    else:
        if value.upper() in ('TRUE', 'YES', 'Y', '1'):
            return True
        else:
            return False

def get_containers_run_conf():
    try:
        with open(MY_CONTAINERS_DIR+'/run.conf') as f:
            content = f.read().replace('\n','').replace('  ',' ')
            registered_containers = json.loads(content)
    except IOError:
        return []
    return registered_containers
 
def is_container_registered(container):
    registered_containers = get_containers_run_conf()   
    for registered_container in registered_containers:
        if registered_container['container'] == container:
            return True
    return False
    
def is_container_running(container, instance):
    '''Returns True if the container is running, False otherwise'''  
    running = ps(container=container, instance=instance, capture=True)
    if running:
        # TODO: imporve this part, return a dict or something from ps
        for item in running [0]:
            if item and item.startswith('Up'):
                return True
    return False

def container_exits_but_not_running(container, instance):
    '''Returns True if the container is existent but not running,, False otherwise'''  
    running = ps(container=container, instance=instance, capture=True, allstates=True)
    if running:
        # TODO: imporve this part, return a dict or something from ps
        for item in running [0]:
            if item and not item.startswith('Up'):
                return True
    return False
    

def setswitch(**kwargs): 
    '''Set a switch according to the default of the instance types, or use the value if set'''
         
    instance = kwargs.pop('instance')    
    for i, swicth in enumerate(kwargs):
        
        if kwargs[swicth] is not None:
            # If the arg is alreay set just return it
            return kwargs[swicth]
        else:
            # Else set the defualt value
            try:
                this_defaults = defaults[instance]
            except KeyError:
                this_defaults = defaults['standard']
                
            return this_defaults[swicth]
                
        if i >0:
            raise Exception('Internal error')

def format_shell_error(stdout, stderr, exit_code):
    string  = '\nExit code: {}'.format(exit_code)
    string += '\n-------- STDOUT ----------\n'
    string += stdout
    string += '\n-------- STDERR ----------\n'
    string +=stderr +'\n'
    return string


def get_container_ip(container, instance):
    ''' Get the IP address of a given container'''
    
    # Do not use .format as there are too many graph brackets    
    IP = shell('docker inspect --format \'{{ .NetworkSettings.IPAddress }}\' ' + container + '-' +instance, capture=True).stdout
    
    if IP:
        try:
            socket.inet_aton(IP)
        except socket.error:
            raise Exception('Error, I coudl not find a valid IP address for container "{}", instance "{}"'.format(container, instance))
            
    return IP

#--------------------------
# Containers management
#--------------------------


@task
def build(container=None, progress=False, debug=False):
    '''Build a given container. If container name is set to "all" then builds all the containers'''

    # Sanitize...
    (container, instance) = sanity_checks(container)

    # Switches
    progress = booleanize(progress=progress)
    debug    = booleanize(progress=progress)
    
    # Handle debug swicth:
    if debug:
        logger.setLevel(logging.DEBUG)  
    
    if container.upper()=='ALL':
        # Build everything then obtain which containers we have to build
        
        print '\nBuilding all containers'
        
        try:
            with open(MY_CONTAINERS_DIR+'/build.conf') as f:
                content = f.read().replace('\n','').replace('  ',' ')
                containers_to_build = json.loads(content)
        except Exception, e:
            abort('Got error in reading build.conf for automated building: {}'.format(e))
        
        # Recursevely call myself
        for container in containers_to_build:
            build(container=container, progress=progress)
    
    else:
        # Build a given container
        print '\nBuilding container "{}"'.format(container)
        
        
        # Check for required files
        print 'Getting remote files...'
        
        # Build command 
        build_command = 'cd ' + get_container_dir(container) + '/.. &&' + 'docker build -t dockerops/' + container + ' ' + container
        
        # Build
        print 'Building...'
        if progress:
            shell(build_command, progress=True)
        else:
            if shell(build_command, progress=False, capture=False, silent=True):
                print 'Build OK'
            else:
                abort('Something happened')



@task
def start(container,instance):
    if container_exits_but_not_running(container,instance):
        shell('docker start {}-{}'.format(container,instance), silent=True)
    else:
        abort('Cannot start a container in not exited state. use "run" instead')


@task
def run(container=None, instance=None, persistent_data=None, persistent_log=None, persistent_opt=None, safemode=False, expose_ports=False, linked=None, interactive=False, seed_command=None, debug=False):
    '''Run a given container with a given instance. In no instance name is set,
    a standard insatnce with a random name is run. If container name is set to "all"
    then all the containers are run, according  to the run.conf file.'''
    
    # Sanitize...
    (container, instance) = sanity_checks(container, instance)
        
    if container == 'all':
        
        # Check for build.conf
                 
        try:
            with open(MY_CONTAINERS_DIR+'/run.conf') as f:
                content = f.read().replace('\n','').replace('  ',' ')
                containers_to_run_confs = json.loads(content)
        except Exception, e:
            abort('Got error in reading run.conf for automated execution: {}'.format(e))
        
        for container_conf in containers_to_run_confs:
            
            # Recursively call myself with proper args. The args of the call always win over the configuration(s)
            run(container       = container_conf['container'],
                instance        = container_conf['instance'],
                persistent_data = persistent_data if persistent_data is not None else (container_conf['persistent_data'] if 'persistent_data' in container_conf else None),
                persistent_log  = persistent_log  if persistent_log  is not None else (container_conf['persistent_log']  if 'persistent_log'  in container_conf else None),
                persistent_opt  = persistent_opt  if persistent_opt  is not None else (container_conf['persistent_opt']  if 'persistent_opt'  in container_conf else None),
                expose_ports    = expose_ports    if expose_ports    is not None else (container_conf['expose_ports']    if 'expose_ports'    in container_conf else None),
                linked          = linked          if linked          is not None else (container_conf['linked']          if 'linked'          in container_conf else None),
                safemode        = safemode,
                debug           = debug)
                
        # Exit
        return

    # Handle debug swicth:
    if booleanize(debug=debug):
        logger.info('Setting loglevel to DEBUG from now on..')
        logger.setLevel(logging.DEBUG)      

    # Run a specific container
    print '\nRunning container "{}", instance "{}"...'.format(container,instance)

    # Set switches
    linked          = setswitch(linked=linked, instance=instance)
    persistent_data = setswitch(persistent_data=persistent_data, instance=instance)
    persistent_log  = setswitch(persistent_log=persistent_log, instance=instance)
    persistent_opt  = setswitch(persistent_opt=persistent_opt, instance=instance)
    expose_ports    = setswitch(expose_ports=expose_ports, instance=instance)
    safemode        = setswitch(safemode=safemode, instance=instance)

    # Check if this container is already running
    if is_container_running(container,instance):
        print 'Container is already running, not starting.'
        # Exit
        return        
    
    # Check if this container is exited
    if container_exits_but_not_running(container,instance):
        if instance=='safemode':
            # Only for safemode instances we take the right of cleaning
            shell('fab clean:{},isnatnce=safemode'.format(container), silent=True)
        else:
            abort('Container "{0}", instance "{1}" exists but it is not running, I cannot start it since the linking would be end up broken. Use fab clean:{0},instance={1} to clean it and start over clean, or fab start:{0},instance={1} if you know what you are doing.'.format(container,instance))
  
    # Obtain env vars to set. First, the always present ones
    ENV_VARs = {
                'CONTAINER': container,
                'INSTANCE':  instance,
                'PERSISTENT_DATA': persistent_data,
                'PERSISTENT_LOG': persistent_data,
                'PERSISTENT_OPT': persistent_data,
                }
    
    # Check if this container is listed in the run.conf:
    if is_container_registered(container):
        
        # If the container is registered, the the rules of the run.conf applies, so:
        
        container_conf = None
        requested_ENV_VARs = {}    
        
        # 1) Read the conf if any
        try:
            with open(MY_CONTAINERS_DIR+'/run.conf') as f:
                content = f.read().replace('\n','').replace('  ',' ')
                containers_to_run_confs = json.loads(content)
        except Exception, e:
            abort('Got error in reading run.conf for loading container info: {}'.format(e))        
    
        for item in containers_to_run_confs:
            if (container == item['container']) and instance == item['instance']:
                logger.debug('Found conf for container "%s", instance "%s"', container, instance)
                container_conf = item 
            
        # 2) Now, enumerate the vars required by this container:
        if container_conf and 'env_vars' in container_conf:
            requested_ENV_VARs = {var:container_conf['env_vars'][var] for var in container_conf['env_vars']} if 'env_vars' in container_conf else {}
            if instance == 'master':
                logger.debug('adding to the required ENV VARs also the linking ones since the instance is a master one')
                if 'linked' in container_conf:
                    for linked_container in container_conf['linked']:
                        # Add this var flagged as unset
                        requested_ENV_VARs[linked_container['link']+'_ENV_HOST_IP'] = None 
        
        # 3) Try to set them from the env:
        for requested_ENV_VAR in requested_ENV_VARs.keys():
            if requested_ENV_VAR is None:
                requested_ENV_VARs[requested_ENV_VAR] = os.getenv(requested_ENV_VAR, None)
                

        # Do we still have missing values?
        if None in requested_ENV_VARs.values():
            logger.debug('After checking the env I still cannot find some requred env vars, proceeding with the host conf')
        
            host_conf = None  
            for requested_ENV_VAR in requested_ENV_VARs:

                if requested_ENV_VARs[requested_ENV_VAR] is None:
                    if host_conf is None:
                        # Try to load the host conf:
                        try:
                            with open(MY_CONTAINERS_DIR+'/host.conf') as f:
                                content = f.read().replace('\n','').replace('  ',' ')
                                host_conf = json.loads(content)
                        except ValueError,e:
                            abort('Cannot read conf in {}. Fix parsing or just remove the file and start over.'.format(MY_CONTAINERS_DIR+'/host.conf'))  
                        except IOError, e:
                            host_conf = {}
                            
                    # Try to see if we can set this var accoridng to the conf
                    if requested_ENV_VAR in host_conf:
                        requested_ENV_VARs[requested_ENV_VAR] = host_conf[requested_ENV_VAR]
                    else:
                        # Ask the user for the value of this var
                        host_conf[requested_ENV_VAR] = raw_input('Please enter a value for the required ENV VAR "{}":'.format(requested_ENV_VAR))
                        requested_ENV_VARs[requested_ENV_VAR] = host_conf[requested_ENV_VAR]
                        
                        # Then, dump the conf #TODO: dump just at the end..
                        with open(MY_CONTAINERS_DIR+'/host.conf', 'w') as outfile:
                            json.dump(host_conf, outfile)
                    

    
        # Handle master instance non registered.
        if instance == 'master' and not is_container_registered(container):
            abort('Sorry, a master instance not registered is not yet supported. \
                  The idea is to look in the entrypoint to obtain the ports to expose')
            
    # Start building run command
    run_cmd = ''
    
    # TODO: is this approach still required?
    #for ENV_VAR in ENV_VARs:
    #    if isinstance(ENV_VAR, bool) or isinstance(ENV_VAR, float) or isinstance(ENV_VAR, int):
    #        run_cmd += 'export {}={} && '.format(ENV_VAR, ENV_VARs[ENV_VAR])
    #    else:
    #        run_cmd += 'export {}="{}" && '.format(ENV_VAR, str(ENV_VARs[ENV_VAR]))
       
    run_cmd += 'docker run --name {}-{} '.format(container,instance)

    # Handle linking...
    if linked:
        if container_conf and 'links' in container_conf:
            for link in container_conf['links']:
                
                # Shortcuts
                link_name      = link['name']
                link_container = link['container']
                link_instance  = link['instance']

                # Validate: detet if there is a running container for link['container'], link['instance']
                if link_instance:
                    # If a given instance name has been specified, we just need to check taht this container is running with this instance
                    
                    if not is_container_running(link_container, link_instance):
                        abort('Could not find the container "{}", instance "{}" which is required for linking by container "{}", instance "{}"'.format(link_container, link_instance, container, instance))             
  
                else:
                    
                    # Obtain any running instance
                    running_instances = get_running_instances_matching(link_container)         
                    if len(running_instances) == 0:
                        abort('Could not find any running instance of container "{}" which is required for linking by container "{}", instance "{}"'.format(link_container, container, instance))             
                    if len(running_instances) > 1:
                        logger.info('Found more than one running instance for container "{}" which is required for linking: {}. I will use the first one ({})..'.format(link_container, running_instances, running_instances[0]))   
                    link_instance = running_instances[0]

                # Now add linking flag for this link
                run_cmd += ' --link {}:{}'.format(link_container+'-'+link_instance, link_name)
                
                # Also, add an env var with the linked container IP
                ENV_VARs[link_name+'_CONTAINER_IP'] = get_container_ip(link_container, link_instance)

    # Add env vars..
    for ENV_VAR in ENV_VARs:  
        # TODO: all vars are inderstood as strings. Why?  
        if isinstance(ENV_VAR, bool) or isinstance(ENV_VAR, float) or isinstance(ENV_VAR, int):
            run_cmd += ' -e {}={}'.format(ENV_VAR, ENV_VARs[ENV_VAR])
        else:
            run_cmd += ' -e {}="{}"'.format(ENV_VAR, str(ENV_VARs[ENV_VAR]))

    # Handle safemode
    if safemode or instance=='safemode':
        interactive=True

    # Set seed command
    if not seed_command:
        if interactive:
            seed_command = 'bash'
        else:
            seed_command = 'supervisord'

    # Run!
    logger.debug('Command: %s', run_cmd) 
    if interactive:
        print 'here'
        run_cmd += ' -i -t dockerops/{}:latest {}'.format(container, seed_command)
        local(run_cmd)
        shell('fab clean:container={},instance={}'.format(container,instance), silent=True)
        
    else:
        run_cmd += ' -d -t dockerops/{}:latest {}'.format(container, seed_command)   
        if not shell(run_cmd, silent=True):
            abort('Something failed')
        print "Done."
    
 
    
    
@task
def clean(container=None, instance=None):
    '''Clean a given container. If container name is set to "all" then clean all the containers according 
    to the run.conf file. If container name is set to "wide" then all containers on th host are cleaned'''
    
    # Sanitize...
    (container, instance) = sanity_checks(container,instance)
    
    #all: list containers to clean (check run.conf first)
    #wide: warn and clean all
    
    if container == 'wide':
        
        print ''
        if confirm('Clean containers widely? WARNING: this will stop and remove *really all* Docker containers running on this system!'):
            print 'Cleaning all Docker containers on the system...'
            shell('docker stop $(docker ps -a -q) &> /dev/null', silent=True)
            shell('docker rm $(docker ps -a -q) &> /dev/null', silent=True)

    elif container == 'all':
        
        print ('\nThis action will clean the following containers intances:')
        # Get container list to clean
        containers_run_conf = get_containers_run_conf()
        for container_conf in containers_run_conf:
            print ' - container "{}", instance "{}"'.format(container_conf['container'], container_conf['instance'])

        if confirm('Proceed?'):
            for container_conf in containers_run_conf:
                print 'Cleaning conatiner "{}", instance "{}"..'.format(container_conf['container'], container_conf['instance'])          
                shell("docker stop "+container_conf['container']+"-"+container_conf['instance']+" &> /dev/null", silent=True)
                shell("docker rm "+container_conf['container']+"-"+container_conf['instance']+" &> /dev/null", silent=True)
                        
    else:
        if not instance:
            abort('Cleanng a given container without providing an instance is not yet supported')
        else:
            shell("docker stop "+container+"-"+instance+" &> /dev/null", silent=True)
            shell("docker rm "+container+"-"+instance+" &> /dev/null", silent=True)
                            
        
    

@task
def ssh(container=None, instance=None):
    '''SSH into a given container'''
    
    # Sanitize...
    (container, instance) = sanity_checks(container,instance)
    
    try:
        IP = get_container_ip(container, instance)
    except Exception, e:
        abort('Got error when obtaaining IP address for container "{}", instance "{}": "{}"'.format(container,instance, e))
    if not IP:
        abort('Got no IP address for container "{}", instance "{}"'.format(container,instance))

    # Check if the key has proper permissions
    if not shell('ls -l keys/id_rsa',capture=True).stdout.endswith('------'):
        shell('chmod 600 keys/id_rsa', silent=True)

    shell(command='ssh -oStrictHostKeyChecking=no -i keys/id_rsa dockerops@' + IP, interactive=True)

@task
def help():
    shell('fab --list', capture=False)

@task
def ip(container=None, instance=None):

    # Sanitize...
    (container, instance) = sanity_checks(container,instance)
    
    # TODO: add the IP columns in ps?
    print 'IP address for container: ', get_container_ip(container, instance)


# TODO: split in function plus task, allstates goes in the function
@task
def ps(container=None, instance=None, capture=False, allstates=False):
    '''Info on runnign containers. Give a container name to obtain informations only about that specific container.
    Use the magic words 'all' to list also the not running ones, and 'wide' to list also the containers not managed by
    DockerOps (both running and not running)'''

    # Handle magic words all and wide
    if container or allstates:# in ['all', 'wide']:
        out = shell('docker ps -a', capture=True)
        
    else:
        out = shell('docker ps', capture=True)
    
    # If error:
    if out.exit_code != 0:
        print format_shell_error(out.stdout, out.stderr, out.exit_code)
    
    # Handle wide filtering
    if container != 'wide':
        known_containers = [conf['container'] for conf in get_containers_run_conf()]
    else:
        known_containers = None
    
    index=[]
    content=[]
    
    # TODO: improve, use the first char position of the index to parse. Also, use a better coding please..!    
    for line in str(out.stdout).split('\n'):
        if not index:
            count = 0
            for item in str(line).split('  '):
                if item:    
                    if item[0]==' ':
                        item = item[1:]

                    if item[-1]==' ':
                        item = item[:-1]
                    
                    # Obtain container_name_position
                    if item == 'NAMES':
                        container_name_position = count
                        
                    count += 1
                    index.append(item)
                    
        else:
            count = 0
            line_content = []
            for item in str(line).split('  '):
                if item:
                    count += 1
                    if item[0]==' ':
                        item = item[1:]

                    if item[-1]==' ':
                        item = item[:-1]                    
                    # Parse container name
                    
                    line_content.append(item)
                    # DEBUGprint count, item
                           
            if len(line_content) == 6:
                line_content.append(line_content[5])
                line_content[5] = None


            # Convert container names
            for i, item in enumerate(line_content):
                if i == container_name_position:

                    # If a containe name was given, filter against it:
                    if container and (not container in ['all', 'wide']):
                        if item.startswith(container):
                            if instance and not item.endswith('-'+instance):
                                continue
                        else:
                            continue
                        
                    if instance:
                        if item.endswith('-'+instance):
                            pass
                        else: 
                            continue
 
                    # Handle Dockerops containers container 
                    if ('-' in item):
                        if known_containers is not None:
                            # Filter against known_containers
                            if item.split('-')[0] not in known_containers:
                                logger.info('Skipping container "{}" as it is not recognized by DockerOps. Use the "all" magic word to list them'.format(item))
                                continue
                            else:
                                # Add it
                                instance = item.split('-')[-1]
                                item = '-'.join(item.split('-')[0:-1]) + ',instance='+str(instance)
                                line_content[container_name_position] = item
                                content.append(line_content)    
                                
                            
                        else:
                            # Add it
                            instance = item.split('-')[-1]
                            item = '-'.join(item.split('-')[0:-1]) + ',instance='+str(instance)
                            line_content[container_name_position] = item
                            content.append(line_content)
                            
                    # Handle non-Dockerops containers 
                    else:
                        if container=='wide': 
                            line_content[container_name_position] = item
                            content.append(line_content)
                        else:
                            continue
  
                    
    
    #-------------------
    # Print output
    #-------------------
    if not capture:
        print ''
        # Prepare 'stats' 
        fields=['CONTAINER ID', 'NAMES', 'IMAGE', 'STATUS']
        max_lenghts = []
        positions = []
        
        for i, item in enumerate(index):
            if item in fields:
                positions.append(i)
                max_lenght=0
            
                for entry in content:
                    
                    if entry[i] and (len(entry[i])>max_lenght):
                        max_lenght = len(entry[i])
                max_lenghts.append(max_lenght)
    
        # Print index
        cursor=0
        for i, item in enumerate(index):
            if i in positions:
                print item,
                # How many spaces?
                spaces = max_lenghts[cursor] - len(item)
                
                if spaces>0:
                    for _ in range(spaces):
                        print '',
    
                cursor+=1
        print ''
        
        # Print List 
        for entry in content:
            cursor=0
            for i, item in enumerate(entry):
                if i in positions:
                    print item,
                    # How many spaces?
                    spaces = max_lenghts[cursor] - len(item)
                    
                    if spaces>0:
                        for _ in range(spaces):
                            print '',
        
                    cursor+=1
            print ''
    
        # Print output and stderr if any
        print out.stderr
        
    else:
        return content

















