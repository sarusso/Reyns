#--------------------------
# Imports
#--------------------------

import os
import inspect
import uuid
import logging
import json
import socket
import fcntl
import struct

from fabric.utils import abort
from fabric.operations import local
from fabric.api import task
from fabric.contrib.console import confirm
from subprocess import Popen, PIPE
from collections import namedtuple
from time import sleep


#--------------------------
# Conf
#--------------------------

PROJECT_NAME        = os.getenv('PROJECT_NAME', 'dockerops').lower()
PROJECT_DIR         = os.getenv('PROJECT_DIR', os.getcwd())
DATA_DIR            = os.getenv('DATA_DIR', PROJECT_DIR + '/data_' + PROJECT_NAME)
APPS_CONTAINERS_DIR = os.getenv('APPS_CONTAINERS_DIR', os.getcwd() + '/apps_containers')
BASE_CONTAINERS_DIR = os.getenv('BASE_CONTAINERS_DIR', os.getcwd() + '/base_containers')
LOG_LEVEL           = os.getenv('LOG_LEVEL', 'INFO')


# Defaults   
defaults={}
defaults['master']    = {'linked':True,  'persistent_data':True,  'persistent_opt': False, 'persistent_log':True,  'publish_ports':True,  'safemode':False}
defaults['published'] = {'linked':True,  'persistent_data':False, 'persistent_opt': False, 'persistent_log':False, 'publish_ports':True,  'safemode':False}
defaults['standard']  = {'linked':True,  'persistent_data':False, 'persistent_opt': False, 'persistent_log':False, 'publish_ports':False, 'safemode':False}


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
      
# Get IP address of an interface              
def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])


# More verbose json error message
json_original_errmsg = json.decoder.errmsg
def json_errmsg_plus_verbose(msg, doc, pos, end=None):
    json.last_error_verbose = doc[pos-15:pos+15].replace('\n','').replace('  ',' ')
    return json_original_errmsg(msg, doc, pos, end)
json.decoder.errmsg = json_errmsg_plus_verbose


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
            abort('You must provide the container name or use the magic words "all" or "reallyall"') 
        else:
            abort('You must provide the container name or use the magic word "all"')
    
    # Check instance name     
    if not instance:
        if run:
            instance = str(uuid.uuid4())[0:8]
            
        if ssh or (clean and not container in ['all', 'reallyall']):
            running_instances = get_running_containers_instances_matching(container)
            if len(running_instances) == 0:
                abort('Could not find any running instance of container matching "{}"'.format(container))                
            if len(running_instances) > 1:
                if clean:
                    abort('Found more than one running instance for container "{}": {}, please specity wich one.'.format(container, running_instances))            
                else:         
                    if not confirm('WARNING: I found more than one running instance for container "{}": {}, i will be using the first one ("{}"). Proceed?'.format(container, running_instances, running_instances[0])) :
                        abort('Stopped.')
            container = running_instances[0][0]
            instance  = running_instances[0][1]
        
    if instance and build:
        abort('The build command does not make sense with an instance name (got "{}")'.format(instance))
    
    
    # Avoid 'reallyall' name if building'
    if build and container == 'reallyall':
        abort('Sorry, you cannot use the word "reallyall" as a container name as it is reserverd.')
    
    # Check container source if build:
    if build and container != 'all':
        
        container_dir = get_container_dir(container)
        if not os.path.exists(container_dir):
            abort('I cannot find this container ("{}") source directory. Are you in the project\'s root? I was looking for "{}".'.format(container, container_dir))
            
    return (container, instance)


def get_running_containers_instances_matching(container,instance=None):
    '''Return a list of [container_name, instance_name] matching the request.
    Examples args:
      container = postgres_2.4, instanceo=one
      container = postgres_2.4, instanceo=None
      container = postgres_*,instance=one
      container = postgres_*,instance=None'''
    running =  info(container=container, instance=instance, capture=True)
    instances = []
    if running:
        
        # TODO: Again, ps with capture on returns a list but should return a dict.
        for container in running:
            fullname = container[-1]
            if ',instance=' in fullname:
                found_container = fullname.split(',')[0]
                found_instance  = fullname.split('=')[1]
                instances.append([found_container,found_instance])
                
            elif '-' in fullname:
                raise Exception('Deprecated, fix me!!')
            else:
                logger.warning('Got unknown name format from ps: "{}"'.format(fullname))
               
            
    return instances


def get_container_dir(container=None):
    if not container:
        raise Exception('get_container_dir: container is required, got "{}"'.format(container))
    if container in ['dockerops-common', 'dockerops-base', 'dockerops-dns']:
        return BASE_CONTAINERS_DIR + '/' + container
    else:
        return APPS_CONTAINERS_DIR + '/' + container



def shell(command, capture=False, progress=False, interactive=False, silent=False):
    '''Execute a command in the shell. By default prints everything. If the capture switch is set,
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
    
    # Handle shortcut: an arg with its name equal to its value is considered as True
    if name==value:
        return True
    
    if isinstance(value, bool):
        return value
    else:
        if value.upper() in ('TRUE', 'YES', 'Y', '1'):
            return True
        else:
            return False

def get_containers_run_conf(conf_file=None):
    
    conf_file = 'run.conf' if not conf_file else conf_file
    try:
        with open(APPS_CONTAINERS_DIR+'/'+conf_file) as f:
            content = f.read()#.replace('\n','').replace('  ',' ')
            json_content = []
            # Handle comments
            for line in content.split('\n'):
                if '#' in line:
                    line = line.split('#')[0]
                json_content.append(line)     
            json_content = '\n'.join(json_content)
            try:
                registered_containers = json.loads(json_content)
            except ValueError as e:
                try:
                    # Try to improve the error message
                    json_error_msg_verbose = getattr(json, 'last_error_verbose')
                    raise ValueError( str(e) + '; error in proximity of: ', json_error_msg_verbose) 
                except:
                    # Otherwise, just raise...
                    raise e
    except IOError:
        # If the conf file was explicitly set, then raise, otherwise just return empty conf
        if conf_file != 'run.conf':
            raise
        else:
            return []
    return registered_containers
 
def is_container_registered(container, conf=None):
    registered_containers = get_containers_run_conf(conf)   
    for registered_container in registered_containers:
        if registered_container['container'] == container:
            return True
    return False
    
def is_container_running(container, instance):
    '''Returns True if the container is running, False otherwise'''  
    running = info(container=container, instance=instance, capture=True)

    if running:
        # TODO: improve this part, return a dict or something from ps
        for item in running [0]:
            if item and item.startswith('Up'):
                return True
    return False

def container_exits_but_not_running(container, instance):
    '''Returns True if the container is existent but not running, False otherwise'''  
    running = info(container=container, instance=instance, capture=True)
    if running:
        # TODO: improve this part, return a dict or something from ps
        for item in running[0]:
            if item and item.startswith('Up'):
                return False
        return True
    return False
    

def setswitch(**kwargs): 
    '''Set a switch according to the default of the instance types, or use the value if set'''
         
    instance_type = kwargs.pop('instance_type')    
    for i, swicth in enumerate(kwargs):
        
        if kwargs[swicth] is not None:
            # If the arg is already set just return it (booleanizing)
            return booleanize(kwargs[swicth])
        else:
            # Else set the default value
            try:
                this_defaults = defaults[instance_type]
            except KeyError:
                logger.warning('I have to fallback on standar instance type as I could not find the value for this instance type')
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
    IP = shell('docker inspect --format \'{{ .NetworkSettings.IPAddress }}\' ' + PROJECT_NAME + '-' + container + '-' +instance, capture=True).stdout
    
    if IP:
        try:
            socket.inet_aton(IP)
        except socket.error:
            raise Exception('Error, I could not find a valid IP address for container "{}", instance "{}"'.format(container, instance))
            
    return IP



#--------------------------
# Installation management
#--------------------------

@task
def install(how=''):
    '''Install DockerOps (user/root)'''
    shell(os.getcwd()+'/install.sh {}'.format(how), interactive=True)

@task
def uninstall(how=''):
    '''Uninstall DockerOps (user/root)'''
    shell(os.getcwd()+'/uninstall.sh {}'.format(how), interactive=True)

@task
def version():
    '''Get DockerOps version (Git shor hash)'''
    
    last_commit_info = shell('cd ' + os.getcwd() + ' && git log | head -n3', capture=True).stdout
    if not last_commit_info:
        abort('Error: could not determine the version using git')
    last_commit_info_lines = last_commit_info.split('\n')
    commit_shorthash = last_commit_info_lines[0].split(' ')[1][0:7]
    commit_date      = last_commit_info_lines[-1].replace('  ', '')
    print '\nDockerOps version: ' + commit_shorthash + ' (' + commit_date + ')'

@task
def install_demo():
    '''install the DockerOps demo in a directory named 'dockerops-demo' in the current path'''
    
    INSTALL_DIR = PROJECT_DIR + '/dockerops-demo'
    
    print '\nInstalling DockerOps demo in current directory ({})...'.format(INSTALL_DIR)
    import shutil

    try:
        os.makedirs(INSTALL_DIR)
    except OSError,e:
        abort('Could not create directory {}: {}'.format(INSTALL_DIR, e))
    
    try:
        shutil.copytree(os.getcwd()+'/apps_containers', INSTALL_DIR + '/apps_containers')
    except OSError,e:
        abort('Could not copy demo data into {}: {}'.format(INSTALL_DIR + '/apps_containers', e))
        
    print '\nDemo installed.'
    print '\nQuickstart: enter into "{}", then:'.format(INSTALL_DIR)
    print '  - to build it, type "dockerops build:all";'
    print '  - to run it, type "dockerops run:all";'
    print '  - to see running containers, type "dockerops ps";'
    print '  - to ssh into the "dockerops-base", instance "two" container, type "dockerops ssh:dockerops-base,instance=one";'
    print '    - to ping container "dockerops-base", instance "two", type: "ping dockerops-base-two";'
    print '    - to exit ssh type "exit";'
    print '  - to stop the demo, type "dockerops clean:all".'


#--------------------------
# Containers management
#--------------------------

@task
def init(verbose=False, progress=False):
    
    # Switches
    progress = booleanize(progress=progress)
    verbose  = booleanize(verbose=verbose)

    # Build dockerops containers
    build(container='dockerops-common', progress=progress)
    build(container='dockerops-base', progress=progress)
    build(container='dockerops-dns', progress=progress)

@task
def build(container=None, verbose=False, progress=False, debug=False):
    '''Build a given container. If container name is set to "all" then builds all the containers'''

    # Sanitize...
    (container, instance) = sanity_checks(container)

    # Switches
    progress = booleanize(progress=progress)
    verbose  = booleanize(verbose=verbose)
    debug    = booleanize(progress=progress)
    
    # Backcomp #TODO: remove 'progress'
    if verbose:
        progress = True
    
    # Handle debug swicth:
    if debug:
        logger.setLevel(logging.DEBUG)  
    
    if container.upper()=='ALL':

        # Build everything then obtain which containers we have to build        
        print '\nBuilding all containers in {}'.format(APPS_CONTAINERS_DIR)
        
        try:
            with open(APPS_CONTAINERS_DIR+'/build.conf') as f:
                content = f.read().replace('\n','').replace('  ',' ')
                containers_to_build = json.loads(content)
        except Exception, e:
            abort('Got error in reading build.conf for automated building: {}'.format(e))
        
        # Recursevely call myself
        for container in containers_to_build:
            build(container=container, progress=progress)
    
    else:
        # Build a given container
        print '\nBuilding container "{}" as "{}/{}"'.format(container, PROJECT_NAME, container)
                
        # TODO: Check for required files. Use a local Cache? use a checksum? Where to put the conf? a files.json in container's source dir?
        # print 'Getting remote files...'
        
        # Build command 
        build_command = 'cd ' + get_container_dir(container) + '/.. &&' + 'docker build -t ' + PROJECT_NAME +'/' + container + ' ' + container
        
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
    '''Start a stopped container. Use only if you know what you are doing.''' 
    if container_exits_but_not_running(container,instance):
        shell('docker start {}-{}'.format(container,instance), silent=True)
    else:
        abort('Cannot start a container not in exited state. use "run" instead')


@task
# TODO: clarify difference between False and None.
def run(container=None, instance=None, group=None, instance_type=None,
        persistent_data=None, persistent_log=None, persistent_opt=None,
        publish_ports=None, linked=None, seed_command=None, 
        safemode=False,  interactive=False, debug=False, conf=None):
    '''Run a given container with a given instance. In no instance name is set,
    a standard instance with a random name is run. If container name is set to "all"
    then all the containers are run, according  to the run conf file.'''

    #---------------------------
    # Run a group of containers
    #---------------------------
    if container == 'all' or group:
        
        if container == 'all':
            print 'WARNING: using the magic keyword "all" is probably going to be deprecated, use group=all instead.'
            group = 'all'
        
        print '\nRunning containers in {} for group {}'.format(APPS_CONTAINERS_DIR,group)

        if safemode or interactive:
            abort('Sorry, you cannot set one of the "safemode" or "interactive" switches if you are running more than one container') 

        # Load run conf             
        try:
            containers_to_run_confs = get_containers_run_conf(conf)
        except Exception, e:
            abort('Got error in reading run conf for automated execution: {}.'.format(e))
        
        if not containers_to_run_confs:
            abort('No or empty run.conf found, are you in the project\'s root?')
        
        for container_conf in containers_to_run_confs:
            
            # Check for container group.
            # We will run the container if:
            # a) the group is set to 'all'
            # b) the group is set to 'x' and the container group is 'x'            
            if group != 'all':
                if 'group' in container_conf:
                    if container_conf['group'] != group:
                        continue
                else:
                    continue
                
            # Check for container name
            if 'container' not in container_conf:
                abort('Missing container name for conf: {}'.format(container_conf))
            else:
                container = container_conf['container']
                
            # Check for instance name
            if 'instance' not in container_conf:
                abort('Missing instance name for conf: {}'.format(container_conf))
            else:
                instance = container_conf['instance']

            # Handle the instance type.
            if 'instance_type' in container_conf:
                    instance_type = container_conf['instance_type']
            else:
                instance_type = None

            # Recursively call myself with proper args. The args of the call always win over the configuration(s)
            run(container       = container,
                instance        = instance,
                instance_type   = instance_type,
                persistent_data = persistent_data if persistent_data is not None else (container_conf['persistent_data'] if 'persistent_data' in container_conf else None),
                persistent_log  = persistent_log  if persistent_log  is not None else (container_conf['persistent_log']  if 'persistent_log'  in container_conf else None),
                persistent_opt  = persistent_opt  if persistent_opt  is not None else (container_conf['persistent_opt']  if 'persistent_opt'  in container_conf else None),
                publish_ports   = publish_ports   if publish_ports   is not None else (container_conf['publish_ports']   if 'publish_ports'   in container_conf else None),
                linked          = linked          if linked          is not None else (container_conf['linked']          if 'linked'          in container_conf else None),
                interactive     = interactive,
                safemode        = safemode,
                debug           = debug,
                conf            = conf)
                
        # Exit
        return

    #-----------------------
    # Run a given container
    #-----------------------
    
    # Sanitize...
    (container, instance) = sanity_checks(container, instance)
      
    # Handle debug switch:
    if booleanize(debug=debug):
        logger.info('Setting loglevel to DEBUG from now on..')
        logger.setLevel(logging.DEBUG)      

    # Run a specific container
    print '\nRunning container "{}" ("{}/{}"), instance "{}"...'.format(container, PROJECT_NAME, container, instance)

    # Check if this container is exited
    if container_exits_but_not_running(container,instance):

        if interactive:
            # Only for instances run in interactive mode we take the right of cleaning
            shell('fab clean:{},instance=safemode'.format(container), silent=True)

        abort('Container "{0}", instance "{1}" exists but it is not running, I cannot start it since the linking ' \
              'would be end up broken. Use dockerops clean:{0},instance={1} to clean it and start over clean, ' \
              'or dockerops start:{0},instance={1} if you know what you are doing.'.format(container,instance))

    # Check if this container is already running
    if is_container_running(container,instance):
        print 'Container is already running, not starting.'
        # Exit
        return    

    # Init container conf and requested env vars
    container_conf = None
    ENV_VARs       = {}
 
    # Check if this container is listed in the run conf:
    if is_container_registered(container, conf):
        
        # If the container is registered, the the rules of the run conf applies, so:

        # 1) Read the conf if any
        try:
            containers_to_run_confs = get_containers_run_conf(conf)
        except Exception, e:
            abort('Got error in reading run conf for loading container info: {}.'.format(e))        
    
        for item in containers_to_run_confs:
            # The configuration for a given container is ALWAYS applied.
            # TODO: Allow to have different confs per different instances? Could be useful for linking a node with a given server. 
            # i.e. node instance A with server instance A, node instance B with server instance B.
            if instance:
                if (container == item['container'] and instance == item['instance']):
                    logger.debug('Found conf for container "%s", instance "%s"', container, instance)
                    container_conf = item
            else:
                if (container == item['container']):
                    logger.debug('Found conf for container "%s"', container)
                    container_conf = item
        if not container_conf:
            conf_file = conf if conf else 'default (run.conf)'
            if not confirm('WARNING: Could not find conf for container {}, instance {} in the {} conf file. Should I proceed?'.format(container, instance, conf_file)):
                return
        
        # 2) Handle the instance type.
        if container_conf and not instance_type:
            if 'instance_type' in container_conf:
                if container_conf['instance_type'] in ['standard', 'master', 'published']:
                    instance_type = container_conf['instance_type']
                else:
                    abort('Unknown or unapplicable instance type "{}"'.format(instance_type))
            else:
                if container_conf['instance'] in ['master','published','safemode']:
                    instance_type = container_conf['instance']
                else:
                    instance_type = 'standard'
                                          
        # 3) Now, enumerate the vars required by this container:
        if container_conf and 'env_vars' in container_conf:
            ENV_VARs = {var:container_conf['env_vars'][var] for var in container_conf['env_vars']} if 'env_vars' in container_conf else {}
        
        # 4) If instance is master, add also the HOST_IP env var as required if not already set:
        if instance_type == 'master' and not 'HOST_IP' in ENV_VARs:
            ENV_VARs = {'HOST_IP': None}
                
    # Handle instance type for not regitered containers of if not set:
    if not instance_type:
        if instance in ['master','published']:
            instance_type = instance
        else:
            instance_type = 'standard'

    print 'Instance type set to "{}"'.format(instance_type)

    # Set switches (command line values have always the precedence)
    linked          = setswitch(linked=linked, instance_type=instance_type)
    persistent_data = setswitch(persistent_data=persistent_data, instance_type=instance_type)
    persistent_log  = setswitch(persistent_log=persistent_log, instance_type=instance_type)
    persistent_opt  = setswitch(persistent_opt=persistent_opt, instance_type=instance_type)
    publish_ports    = setswitch(publish_ports=publish_ports, instance_type=instance_type)

    # Now add the always present env vars
    ENV_VARs['CONTAINER']       = container
    ENV_VARs['INSTANCE']        = instance
    ENV_VARs['INSTANCE_TYPE']   = instance_type
    ENV_VARs['PERSISTENT_DATA'] = persistent_data
    ENV_VARs['PERSISTENT_LOG']  = persistent_log
    ENV_VARs['PERSISTENT_OPT']  = persistent_opt
    ENV_VARs['SAFEMODE']        = safemode
            
    # Start building run command
    run_cmd = 'docker run --name {}-{}-{} '.format(PROJECT_NAME, container,instance)

    # Handle linking...
    if linked:
        if container_conf and 'links' in container_conf:
            for link in container_conf['links']:

                if not link:
                    continue
              
                # Handle link shortcut
                if isinstance(link, str) or isinstance(link, unicode):
                    
                    if (not '-' in link) or (not ':' in link):
                        abort('Wrong link shortcut string format, cannot find dash or column. See doc.')
                    
                    link_pieces = link.split(':')[0].split('-')
                    
                    # Shortcuts
                    link_name      = link.split(':')[1]
                    link_container = '-'.join(link_pieces[:-1])
                    link_instance  = link_pieces[-1]         
                
                elif isinstance(link, dict):
                    if 'name' not in link:
                        abort('Sorry, you need to give me a link name (ore use the string shortcut for defining it)')
                    if 'container' not in link:
                        abort('Sorry, you need to give me a link container (ore use the string shortcut for defining it)')
                    if 'instance' not in link:
                        abort('Sorry, you need to give me a link instance (ore use the string shortcut for defining it)')
                    
                    # Shortcuts
                    link_name      = link['name']
                    link_container = link['container']
                    link_instance  = link['instance']
                else:
                    abort('Sorry, link must be defining using a dict or a string shortcut (see doc), got {}'.format(link.__class__.__name__))

                
                running_instances = get_running_containers_instances_matching(container)
                
                # Validate: detect if there is a running container for link['container'], link['instance']

                # Obtain any running instances. If link_instance is None, finds all running instances for container and
                # warns if more than one instance is found.
                running_instances = get_running_containers_instances_matching(link_container, link_instance)         
                
                if len(running_instances) == 0:
                    logger.info('Could not find any running instance of container matching "{}" which is required for linking by container "{}", instance "{}". I will expect an env var for proper linking setup'.format(link_container, container, instance))             
                    ENV_VARs[link_name.upper()+'_CONTAINER_IP'] = None
                    
                else:
                    if len(running_instances) > 1:
                        logger.warning('Found more than one running instance for container "{}" which is required for linking: {}. I will use the first one ({}). You can set explicity on which instance to link on in run.conf'.format(link_container, running_instances, running_instances[0]))
                      
                    link_container = running_instances[0][0]
                    link_instance  = running_instances[0][1]
    
                    # Now add linking flag for this link
                    run_cmd += ' --link {}:{}'.format(PROJECT_NAME+'-'+link_container+'-'+link_instance, link_name)
                    
                    # Also, add an env var with the linked container IP
                    ENV_VARs[link_name.upper()+'_CONTAINER_IP'] = get_container_ip(link_container, link_instance)


    # Try to set the env vars from the env (they have always the precedence):
    for requested_ENV_VAR in ENV_VARs.keys():
        requested_ENV_VAR_env_value = os.getenv(requested_ENV_VAR, None)
        if requested_ENV_VAR_env_value:
            logger.debug('Found env var %s with value "%s"', requested_ENV_VAR, requested_ENV_VAR_env_value)
            
            if ENV_VARs[requested_ENV_VAR] is not None:
                print ('WARNING: I am overriding atomaticaly set env var {} (value="{}") and I will use value "{}" as I found it in the env'.format(requested_ENV_VAR, ENV_VARs[requested_ENV_VAR], requested_ENV_VAR_env_value))

            ENV_VARs[requested_ENV_VAR] = requested_ENV_VAR_env_value


    # Check that we have all the required env vars. Do NOT move this section around, it has to stay here.
    if None in ENV_VARs.values():
        logger.debug('After checking the env I still cannot find some required env vars, proceeding with the host conf')
    
        host_conf = None  
        for requested_ENV_VAR in ENV_VARs:
            
            if ENV_VARs[requested_ENV_VAR] is None:
                
                logger.debug('Evaluating required ENV_VAR %s', requested_ENV_VAR)
                
                if host_conf is None:
                    # Try to load the host conf:
                    try:
                        with open(PROJECT_DIR+'/host.conf') as f:
                            content = f.read().replace('\n','').replace('  ',' ')
                            host_conf = json.loads(content)
                    except ValueError,e:
                        abort('Cannot read conf in {}. Fix parsing or just remove the file and start over.'.format(APPS_CONTAINERS_DIR+'/../host.conf'))  
                    except IOError, e:
                        host_conf = {}
                        
                # Try to see if we can set this var according to the conf
                if requested_ENV_VAR in host_conf:
                    logger.debug('Loading ENV_VAR %s from host.conf', requested_ENV_VAR)
                    ENV_VARs[requested_ENV_VAR] = host_conf[requested_ENV_VAR]
                else:
                    
                    logger.debug('ENV_VAR %s not found even in host.conf, now asking the user', requested_ENV_VAR)
                    
                    # Ask the user for the value of this var
                    host_conf[requested_ENV_VAR] = raw_input('Please enter a value for the required ENV VAR "{}" (or export it before launching): '.format(requested_ENV_VAR))
                    ENV_VARs[requested_ENV_VAR] = host_conf[requested_ENV_VAR]
                    
                    # Do we have to save the value for using it the next time? 
                    answer = ''
                    while answer.lower() not in ['y','n']:
                        answer = raw_input('Should I save this value in host.conf for beign automatically used the next time? (y/n): ')
                    
                    if answer == 'y':
                        # Then, dump the conf #TODO: dump just at the end..
                        with open(PROJECT_DIR+'/host.conf', 'w') as outfile:
                            json.dump(host_conf, outfile)

    logger.debug('Done setting ENV vars. Summary: %s', ENV_VARs)

    # Handle the special case for *_IP var names
    found_function = False
    for ENV_VAR in ENV_VARs:
        if ENV_VAR.endswith('_IP'):
            logger.debug('%s ENV_VAR ends with _IP, I am now going to ckeck if I have to apply a function to it...', ENV_VAR)
            
            if ENV_VARs[ENV_VAR].startswith('from_'):
                found_function = True
                
                # Obtain interface
                interface = ENV_VARs[ENV_VAR].split('_')[-1]
                logger.debug('Found function for %s: from(\'%s\').', ENV_VAR, interface)
                 
                try:
                    IP = get_ip_address(str(interface)) # Note: cast unicode to string..
                except IOError:
                    abort('Error: network interface {} set in {} does not exist on the host'.format(interface, ENV_VAR))
                    
                logger.debug('Updating value for %s with IP address %s', ENV_VAR, IP)
                ENV_VARs[ENV_VAR] = IP

    # Prind updated environment:
    if found_function:
        logger.debug('Done apllying functions to ENV vars. New summary: %s', ENV_VARs)

    # Handle persistency
    if persistent_data or persistent_log or persistent_opt:

        # Check project data dir exists:
        if not os.path.exists(DATA_DIR):
            logger.debug('Data dir not existent, creating it.. ({})'.format(DATA_DIR))
            os.makedirs(DATA_DIR)
            
        # Check container instance dir exists:
        container_instance_dir = DATA_DIR + '/' + container + '_' + instance
        if not os.path.exists(container_instance_dir):
            logger.debug('Data dir for container instance not existent, creating it.. ({})'.format(container_instance_dir))
            os.mkdir(container_instance_dir)
        
        # Now mount the dir in /persistent in the Docker: here we just provide a persistent storage in the Docker container.
        # the handling of data, opt and log is done in the Dockerfile.
        run_cmd += ' -v {}:/persistent'.format(container_instance_dir)    

    # Handle extra volumes
    if container_conf and 'volumes' in container_conf:
        volumes = container_conf['volumes'].split(',')
        for volume in volumes:
            run_cmd += ' -v {}'.format(volume)

    # Handle published ports
    if publish_ports:

        # Obtain the ports to publish from the Dockerfile
        try:
            with open(get_container_dir(container)+'/Dockerfile') as f:
                content = f.readlines()
        except IOError:
            abort('No Dockerfile found (?!) I was looking in {}'.format(get_container_dir(container)+'/Dockerfile'))
        
        ports =[]
        udp_ports = []
        for line in content:
            if line.startswith('EXPOSE'):
                # Clean up the line
                line_clean =  line.replace('\n','').replace(' ',',').replace('EXPOSE','')
                for port in line_clean.split(','):
                    if port:
                        try:
                            # Append while validating
                            ports.append(int(port))
                        except ValueError:
                            abort('Got unknown port from container\'s dockerfile: "{}"'.format(port))

            if line.startswith('#UDP_EXPOSE'):
                # Clean up the line
                line_clean =  line.replace('\n','').replace(' ',',').replace('#UDP_EXPOSE','')
                for port in line_clean.split(','):
                    if port:
                        try:
                            # Append while validating
                            udp_ports.append(int(port))
                        except ValueError:
                            abort('Got unknown port from container\'s dockerfile: "{}"'.format(port))

        # Handle forcing of an IP where to publish the port
        pubish_on_ip = ''
        
        if instance == 'master':
            pubish_on_ip = ENV_VARs['HOST_IP']+':'

        # TCP ports publishing
        for port in ports:
            
            internal_port = port
            external_port = port
            run_cmd += ' -p {}{}:{}'.format(pubish_on_ip, internal_port, external_port)

        # UDP ports publishing
        for port in udp_ports:
            internal_port = port
            external_port = port
            run_cmd += ' -p {}{}:{}/udp'.format(pubish_on_ip, internal_port, external_port)

    # Add env vars..
    logger.debug("Adding env vars: %s", ENV_VARs)
    for ENV_VAR in ENV_VARs:  
        # TODO: all vars are understood as strings. Why?  
        if isinstance(ENV_VAR, bool) or isinstance(ENV_VAR, float) or isinstance(ENV_VAR, int):
            run_cmd += ' -e {}={}'.format(ENV_VAR, ENV_VARs[ENV_VAR])
        else:
            run_cmd += ' -e {}="{}"'.format(ENV_VAR, str(ENV_VARs[ENV_VAR]))

    # Handle hostname
    if container_conf and 'hostname' in container_conf:
        run_cmd += ' -h {}'.format(container_conf['hostname'])
    else:
        run_cmd += ' -h {}-{}'.format(container,instance)

    # Set seed command
    if not seed_command:
        if interactive:
            seed_command = 'bash'
        else:
            seed_command = 'supervisord'

    # Default tag prefix to PROJECT_NAME    
    tag_prefix = PROJECT_NAME

    # But if we are running a DockerOps container, use DockerOps image
    if container in ['dockerops-base', 'dockerops-dns', 'dockerops-common']:
        tag_prefix = 'dockerops'

    if interactive:
        run_cmd += ' -i -t {}/{}:latest {}'.format(tag_prefix, container, seed_command)
        local(run_cmd)
        shell('fab clean:container={},instance={}'.format(container,instance), silent=True)
        
    else:
        run_cmd += ' -d -t {}/{}:latest {}'.format(tag_prefix, container, seed_command)   
        if not shell(run_cmd, silent=True):
            abort('Something failed')
        print "Done."
   
    # In the end, the sleep..
    if container_conf and 'sleep' in container_conf:
        to_sleep = int(container_conf['sleep'])
        if to_sleep:
            print "Now sleeping {} seconds to allow container setup...".format(to_sleep)
            sleep(to_sleep)
 
    
    
@task
def clean(container=None, instance=None, group=None, force=False, conf=None):
    '''Clean a given container. If container name is set to "all" then clean all the containers according 
    to the run conf file. If container name is set to "reallyall" then all containers on the host are cleaned'''

    # all: list containers to clean (check run conf first)
    # reallyall: warn and clean all
    
    if container == 'reallyall':
        
        print ''
        if confirm('Clean all containers? WARNING: this will stop and remove *really all* Docker containers running on this host!'):
            print 'Cleaning all Docker containers on the host...'
            shell('docker stop $(docker ps -a -q) &> /dev/null', silent=True)
            shell('docker rm $(docker ps -a -q) &> /dev/null', silent=True)

    elif container == 'all' or group:
        if container == 'all':
            print 'WARNING: using the magic keyword "all" is probably going to be deprecated, use group=all instead.'
            group = 'all'        
        
        
        # Get container list to clean
        one_in_conf = False
        containers_run_conf = []
        for container_conf in get_containers_run_conf(conf):
            
            # Do not clean instances not explicity set in run.conf (TODO: do we want this?)
            if not container_conf['instance']:
                continue
            
            # Do not clean instances not belonging to the group we want to clean
            if group != 'all' and 'group' in container_conf and container_conf['group'] != group:
                continue
            
            # Understand if the container to clean is running
            if is_container_running(container=container_conf['container'], instance=container_conf['instance']) \
              or container_exits_but_not_running(container=container_conf['container'], instance=container_conf['instance']):
                if not one_in_conf:
                    print ('\nThis action will clean the following containers instances according to run conf:')
                    one_in_conf =True  
                print ' - container "{}" ("{}/{}"), instance "{}"'.format(container_conf['container'], PROJECT_NAME, container_conf['container'], container_conf['instance'])
                containers_run_conf.append({'container':container_conf['container'], 'instance':container_conf['instance']})

        # Understand if There is more
        more_runnign_containers_conf = []
        
        for item in ps(capture=True):
            # TODO: let ps return a list of namedtuples..
            container = item[-1].split(',')[0]
            instance  = item[-1].split('=')[1]
            registered = False
            for container_conf in containers_run_conf:
                if container == container_conf['container'] and instance == container_conf['instance']:
                    registered = True
            if not registered:
                more_runnign_containers_conf.append({'container':container, 'instance':instance})
                
        if one_in_conf and more_runnign_containers_conf:
            print '\nMoreover, the following containers instances will be clean as well as part of this project:'
        elif more_runnign_containers_conf:
            print '\nThe following containers instances will be clean as part of this project:'
        else:
            pass

        for container_conf in more_runnign_containers_conf:
            print ' - container "{}" ("{}/{}"), instance "{}"'.format(container_conf['container'], PROJECT_NAME, container_conf['container'], container_conf['instance'])
        
        # Sum the two lists
        containers_to_clean_conf = containers_run_conf + more_runnign_containers_conf
        
        if not containers_to_clean_conf:
            print '\nNothing to clean, exiting..'
            return
        print ''
        if force or confirm('Proceed?'):
            for container_conf in containers_to_clean_conf:
                if not container_conf['instance']:
                    print 'WARNING: I Cannot clean {}, instance='.format(container_conf['container'], container_conf['instance'])
                else:
                    print 'Cleaning container "{}", instance "{}"..'.format(container_conf['container'], container_conf['instance'])          
                    shell("docker stop "+PROJECT_NAME+"-"+container_conf['container']+"-"+container_conf['instance']+" &> /dev/null", silent=True)
                    shell("docker rm "+PROJECT_NAME+"-"+container_conf['container']+"-"+container_conf['instance']+" &> /dev/null", silent=True)
                            
    else:   
        # Sanitize (and dynamically obtain instance)...
        (container, instance) = sanity_checks(container,instance)
        
        if not instance:
            print 'I did not find any running instance to clean, exiting. Please note that if the instance is not running, you have to specify the instance name to let it be clened'
        else:
            print 'Cleaning container "{}", instance "{}"..'.format(container,instance)          
            shell("docker stop "+PROJECT_NAME+"-"+container+"-"+instance+" &> /dev/null", silent=True)
            shell("docker rm "+PROJECT_NAME+"-"+container+"-"+instance+" &> /dev/null", silent=True)
                            
        
    

@task
def ssh(container=None, instance=None):
    '''SSH into a given container'''
    
    # Sanitize...
    (container, instance) = sanity_checks(container,instance)
    
    try:
        IP = get_container_ip(container, instance)
    except Exception, e:
        abort('Got error when obtaining IP address for container "{}", instance "{}": "{}"'.format(container,instance, e))
    if not IP:
        abort('Got no IP address for container "{}", instance "{}"'.format(container,instance))

    # Check if the key has proper permissions
    if not shell('ls -l keys/id_rsa',capture=True).stdout.endswith('------'):
        shell('chmod 600 keys/id_rsa', silent=True)

    shell(command='ssh -oStrictHostKeyChecking=no -i keys/id_rsa dockerops@' + IP, interactive=True)

@task
def help():
    '''Show this help'''
    shell('fab --list', capture=False)

@task
def ip(container=None, instance=None):
    '''Get a container IP'''

    # Sanitize...
    (container, instance) = sanity_checks(container,instance)
    
    # Get running instances
    running_instances = get_running_containers_instances_matching(container)
    # For each instance found print the ip address
    for i in running_instances:
        print 'IP address for {} {}: {}'.format(i[0], i[1], get_container_ip(i[0], i[1]))




# TODO: split in function plus task, allstates goes in the function

@task
def info(container=None, instance=None, capture=False):
    '''Obtain info about a given container'''
    return ps(container=container, instance=instance, capture=capture, info=True)

@task
def ps(container=None, instance=None, capture=False, onlyrunning=False, info=False, conf=None):
    '''Info on running containers. Give a container name to obtain informations only about that specific container.
    Use the magic words 'all' to list also the not running ones, and 'reallyall' to list also the containers not managed by
    DockerOps (both running and not running)'''

    # TODO: this function has to be COMPLETELY refactored. Please do not look at this code.
    # TODO: return a list of namedtuples instead of a list of lists

    known_containers_fullnames          = None

    if not container:
        container = 'project'

    if not info and container not in ['all', 'platform', 'project', 'reallyall']:
        abort('Sorry, I do not understand the command "{}"'.format(container))

    if container == 'platform':
        known_containers_fullnames = [conf['container']+'-'+conf['instancef'] for conf in get_containers_run_conf(conf)]
        
    # Handle magic words all and reallyall
    if onlyrunning: # in ['all', 'reallyall']:
        out = shell('docker ps', capture=True)
        
    else:
        out = shell('docker ps -a', capture=True)
    
    # If error:
    if out.exit_code != 0:
        print format_shell_error(out.stdout, out.stderr, out.exit_code)

    index=[]
    content=[]
    
    # TODO: improve, use the first char position of the index to parse. Also, use a better coding please..!    
    for line in str(out.stdout).split('\n'):
        
        if not index:
            count = 0
            for item in str(line).split('  '):
                
                # Clean...
                if not item or item == '\n' or item == " ":
                    continue
                
                if item:    
                    if item[0]==' ':
                        item = item[1:]

                    if item[-1]==' ':
                        item = item[:-1]
                    
                    # Obtain container_name_position
                    if item == 'NAMES':
                        container_name_position = count
                        
                    if item == 'IMAGE':
                        image_name_position = count    
                        
                        
                    count += 1
                    index.append(item)
                    
        else:
            
            image_name = None
            count = 0
            line_content = []

            for item in str(line).split('  '):
                
                # Clean...
                if not item or item == '\n' or item == " ":
                    continue
                
                if item:
                    count += 1
                    try:
                        #Remove leading and trailing spaces
                        if item[0]==' ':
                            item = item[1:]

                        if item[-1]==' ':
                            item = item[:-1]                  
                    except IndexError:
                        pass
                    
                    line_content.append(item)
                    # DEBUGprint count, item
                           
            if len(line_content) == 6:
                line_content.append(line_content[5])
                line_content[5] = None

            

            # Convert container names
            for i, item in enumerate(line_content):
                
                if i == image_name_position:
                    image_name = item
                    
                if i == container_name_position:

                    # Set container name
                    container_name = item

                    # Filtering against defined dockers
                    # If a container name was given, filter against it:
                    if container and not container in ['all', 'platform', 'project', 'reallyall']:
                        
                        # Here we are filtering
                        if container[-1] == '*':
                            if container_name.startswith(PROJECT_NAME+'-'+container[0:-1]):
                                if instance and not container_name.endswith('-'+instance):
                                    continue
                            else:
                                continue
                        else:
                            if container_name.startswith(PROJECT_NAME+'-'+container+'-'):
                                if instance and not container_name.endswith('-'+instance):
                                    continue
                            else:
                                continue
                        
                    if instance:
                        if container_name.endswith('-'+instance):
                            pass
                        else: 
                            continue
 
                    # Handle Dockerops containers container
                    if ('-' in container_name) and (not container == 'reallyall') and (container_name.startswith(PROJECT_NAME+'-')):
                        if known_containers_fullnames is not None:
                            # Filter against known_containers_fullnames
                            if container_name not in known_containers_fullnames:
                                logger.info('Skipping container "{}" as it is not recognized by DockerOps. Use the "all" magic word to list them'.format(container_name))
                                continue
                            else:
                                
                                # Remove project name:
                                if not container_name.startswith(PROJECT_NAME):
                                    raise Exception('Error: this container ("{}") is not part of this project ("{}")?!'.format(container_name, PROJECT_NAME))
                                container_name = container_name[len(PROJECT_NAME)+1:]    
                                
                                # Add it 
                                container_instance = container_name.split('-')[-1]
                                container_name = '-'.join(container_name.split('-')[0:-1]) + ',instance='+str(container_instance)
                                line_content[container_name_position] = container_name
                                content.append(line_content)    
                                
                        else:
                            
                            # Remove project name:
                            if not container_name.startswith(PROJECT_NAME):
                                raise Exception('Error: this container ("{}") is not part of this project ("{}")?!'.format(container_name, PROJECT_NAME))
                            container_name = container_name[len(PROJECT_NAME)+1:]
                            
                            # Add it
                            container_instance = container_name.split('-')[-1]
                            container_name = '-'.join(container_name.split('-')[0:-1]) + ',instance='+str(container_instance)
                            line_content[container_name_position] = container_name
                            content.append(line_content)
                            
                    # Handle non-Dockerops containers 
                    else:
                        if container=='reallyall': 
                            line_content[container_name_position] = container_name
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

















