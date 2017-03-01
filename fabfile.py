#--------------------------
# Imports
#--------------------------
from __future__ import print_function

import os
import inspect
import uuid
import logging
import json
import socket
import fcntl
import struct
import platform
import re

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
SERVICES_IMAGES_DIR = os.getenv('SERVICES_IMAGES_DIR', os.getcwd() + '/services')
BASE_IMAGES_DIR     = os.getenv('BASE_IMAGES_DIR', os.getcwd() + '/base')
LOG_LEVEL           = os.getenv('LOG_LEVEL', 'INFO')
SUPPORTED_OSES      = ['ubuntu14.04']

# Defaults   
defaults={}
defaults['standard']   = {'linked':True,  'persistent_data':False, 'persistent_opt': False, 'persistent_log':False, 'publish_ports':False, 'safemode':False, 'interactive':False}
defaults['published']  = {'linked':True,  'persistent_data':False, 'persistent_opt': False, 'persistent_log':False, 'publish_ports':True,  'safemode':False, 'interactive':False}
defaults['persistent'] = {'linked':True,  'persistent_data':True,  'persistent_opt': False, 'persistent_log':True,  'publish_ports':False, 'safemode':False, 'interactive':False}
defaults['master']     = {'linked':True,  'persistent_data':True,  'persistent_opt': False, 'persistent_log':True,  'publish_ports':True,  'safemode':False, 'interactive':False}
defaults['debug']      = {'linked':False, 'persistent_data':False, 'persistent_opt': False, 'persistent_log':False, 'publish_ports':False, 'safemode':True,  'interactive':True }


#--------------------------
# Logger
#--------------------------

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s: %(message)s')
#logger = logging.getLogger(__name__)
logger = logging.getLogger('DockerOps')
logger.setLevel(getattr(logging, LOG_LEVEL))



#--------------------------
# Utility functions & vars
#--------------------------

# Are we running on OSX?
def running_on_osx():
    if platform.system().upper() == 'DARWIN':
        return True
    else:
        return False

# Load host conf
def load_host_conf():
    host_conf = {}
    try:
        with open(PROJECT_DIR+'/host.conf') as f:
            content = f.read().replace('\n','').replace('  ',' ')
            host_conf = json.loads(content)
    except ValueError:
        abort('Cannot read conf in {}. Fix parsing or just remove the file and start over.'.format(SERVICES_IMAGES_DIR+'/../host.conf'))  
    except IOError:
        pass
    return host_conf

# Save host conf           
def save_host_conf(host_conf):
    logger.debug('Saving host conf (%s)', host_conf)
    with open(PROJECT_DIR+'/host.conf', 'w') as outfile:
        json.dump(host_conf, outfile)

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


def sanity_checks(service, instance=None):
    
    caller = inspect.stack()[1][3]
    clean = True if 'clean' in caller else False
    build = True if 'build' in caller else False
    run   = True if 'run' in caller else False
    ssh   = True if 'ssh' in caller else False
    ip    = True if 'ip' in caller else False
    
    if not clean and not build and not run and not ssh and not ip:
        raise Exception('Unknown caller (got "{}")'.format(caller))

    # Check service name 
    if not service:
        if clean:
            abort('You must provide the service name or use the magic words "all" or "reallyall"') 
        else:
            abort('You must provide the service name or use the magic word "all"')
    
    # Check not valid chars in service name TODO: Use a regex suitable for a hostname
    if '_' in service:
        abort('Character "_" is not allowed in a service name (got "{}")'.format(service)) 
    
    # Check instance name     
    if not instance:
        if run:
            instance = str(uuid.uuid4())[0:8]
            
        if ssh or (clean and not service in ['all', 'reallyall']):
            running_instances = get_running_services_instances_matching(service)
            if len(running_instances) == 0:
                abort('Could not find any running instance of service matching "{}"'.format(service))                
            if len(running_instances) > 1:
                if clean:
                    abort('Found more than one running instance for service "{}": {}, please specity wich one.'.format(service, running_instances))            
                else:         
                    if not confirm('WARNING: I found more than one running instance for service "{}": {}, i will be using the first one ("{}"). Proceed?'.format(service, running_instances, running_instances[0])) :
                        abort('Stopped.')
            service = running_instances[0][0]
            instance  = running_instances[0][1]
        
    if instance and build:
        abort('The build command does not make sense with an instance name (got "{}")'.format(instance))
    
    
    # Avoid 'reallyall' name if building'
    if build and service == 'reallyall':
        abort('Sorry, you cannot use the word "reallyall" as a service name as it is reserverd.')
    
    # Check service source if build:
    if build and service != 'all':
        
        service_dir = get_service_dir(service)
        if not os.path.exists(service_dir):
            abort('I cannot find this service ("{}") source directory. Are you in the project\'s root? I was looking for "{}".'.format(service, service_dir))
            
    return (service, instance)


def is_base_service(service):
    return (service.startswith('dockerops-common-') or service.startswith('dockerops-base-') or service.startswith('dockerops-dns'))


def get_running_services_instances_matching(service,instance=None):
    '''Return a list of [service_name, instance_name] matching the request.
    Examples args:
      service = postgres_2.4, instanceo=one
      service = postgres_2.4, instanceo=None
      service = postgres_*,instance=one
      service = postgres_*,instance=None'''
    running =  info(service=service, instance=instance, capture=True)
    instances = []
    if running:
        
        # TODO: Again, ps with capture on returns a list but should return a dict.
        for service in running:
            fullname = service[-1]
            if ',instance=' in fullname:
                found_service = fullname.split(',')[0]
                found_instance  = fullname.split('=')[1]
                instances.append([found_service,found_instance])
                
            elif '-' in fullname:
                raise Exception('Deprecated, fix me!!')
            else:
                logger.warning('Got unknown name format from ps: "{}"'.format(fullname))
               
            
    return instances


def get_service_dir(service=None):
    if not service:
        raise Exception('get_service_dir: service is required, got "{}"'.format(service))
    
    # Handle the case for base services
    
    if is_base_service(service):
        return BASE_IMAGES_DIR + '/' + service
    else:
        return SERVICES_IMAGES_DIR + '/' + service


def shell(command, capture=False, verbose=False, interactive=False, silent=False):
    '''Execute a command in the shell. By default prints everything. If the capture switch is set,
    then it returns a namedtuple with stdout, stderr, and exit code.'''
    
    if capture and verbose:
        raise Exception('You cannot ask at the same time for capture and verbose, sorry')
    
    # If verbose or interactive requested, just use fab's local
    if verbose or interactive:
        return local(command)
    
    # Log command
    logger.debug('Shell executing command: "%s"', command)
    
    # Execute command getting stdout and stderr
    # http://www.saltycrane.com/blog/2008/09/how-get-stdout-and-stderr-using-python-subprocess-module/
    
    process          = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
    (stdout, stderr) = process.communicate()
    exit_code        = process.wait()

    # Convert to str (Python 3)
    stdout = stdout.decode(encoding='UTF-8')
    stderr = stderr.decode(encoding='UTF-8')

    # Formatting..
    stdout = stdout[:-1] if (stdout and stdout[-1] == '\n') else stdout
    stderr = stderr[:-1] if (stderr and stderr[-1] == '\n') else stderr

    # Output namedtuple
    Output = namedtuple('Output', 'stdout stderr exit_code')

    if exit_code != 0:
        if capture:
            return Output(stdout, stderr, exit_code)
        else:
            print(format_shell_error(stdout, stderr, exit_code))      
            return False    
    else:
        if capture:
            return Output(stdout, stderr, exit_code)
        elif not silent:
            # Just print stdout and stderr cleanly
            print(stdout)
            print(stderr)
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

def get_required_env_vars(service):
    required_env_vars_file = SERVICES_IMAGES_DIR+'/'+service+'/required_env_vars.json'
    if not os.path.isfile(required_env_vars_file):
        return []
    try:
        with open(required_env_vars_file) as f:
            logger.debug ('Loading required env vars from %s', required_env_vars_file)
            content = f.read()#.replace('\n','').replace('  ',' ')
            json_content = []
            # Handle comments
            for line in content.split('\n'):
                if '#' in line:
                    line = line.split('#')[0]
                json_content.append(line)     
            json_content = '\n'.join(json_content)
            try:
                required_env_vars = json.loads(json_content)
            except ValueError as e:
                try:
                    # Try to improve the error message
                    json_error_msg_verbose = getattr(json, 'last_error_verbose')
                    raise ValueError( str(e) + '; error in proximity of: ', json_error_msg_verbose) 
                except:
                    # Otherwise, just raise...
                    print('Error in deconding {}'.format(json_content))
                    raise e
    except IOError:
        raise IOError('Error when reading conf file {}'.format(required_env_vars_file))

    logger.debug('Loaded required env vars: %s', required_env_vars)
    return required_env_vars

def get_services_run_conf(conf_file=None):
    conf_file = 'run.conf' if not conf_file else conf_file
    
    if os.path.isfile(PROJECT_DIR+'/'+conf_file):
        conf_file_path = PROJECT_DIR+'/'+conf_file
 
    else:
        # If the conf file was explicitly set, then raise, otherwise just return empty conf
        if conf_file != 'run.conf':
            raise IOError('No conf file {} found'.format(conf_file))
        else:
            return []
        
    # Now load it
    try:  
        with open(conf_file_path) as f:
            logger.debug ('Loading conf from %s/%s', PROJECT_DIR, conf_file)
            content = f.read()#.replace('\n','').replace('  ',' ')
            json_content = []
            # Handle comments
            for line in content.split('\n'):
                if '#' in line:
                    line = line.split('#')[0]
                json_content.append(line)     
            json_content = '\n'.join(json_content)
            try:
                registered_services = json.loads(json_content)
            except ValueError as e:
                try:
                    # Try to improve the error message
                    json_error_msg_verbose = getattr(json, 'last_error_verbose')
                    raise ValueError( str(e) + '; error in proximity of: ', json_error_msg_verbose) 
                except:
                    # Otherwise, just raise...
                    print('Error in deconding {}'.format(json_content))
                    raise e
    except IOError:
        raise IOError('Error when reading conf file {}'.format(conf_file_path))
    
    
    # Validate vars
    valid_service_description_keys = ['service','instance','publish_ports','persistent_data','persistent_opt','persistent_log',
                                      'links', 'sleep', 'env_vars', 'instance_type', 'volumes', 'nethost']
    
    for service_description in registered_services:
        for key in service_description:
            # TODO: Chek minimal subset of required keys, like "service" and "instance" 
            if key not in valid_service_description_keys:
                raise Exception('Error: key "{}" for "{}" service description is not valid'.format(key, service_description['service']))

    # Ok return
    return registered_services
 
def is_service_registered(service, conf=None):
    registered_services = get_services_run_conf(conf)   
    for registered_service in registered_services:
        if registered_service['service'] == service:
            return True
    return False
    
def is_service_running(service, instance):
    '''Returns True if the service is running, False otherwise'''  
    running = info(service=service, instance=instance, capture=True)

    if running:
        # TODO: improve this part, return a dict or something from ps
        for item in running [0]:
            if item and item.startswith('Up'):
                return True
    return False

def service_exits_but_not_running(service, instance):
    '''Returns True if the service is existent but not running, False otherwise'''  
    running = info(service=service, instance=instance, capture=True)
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
    string += str(stdout)
    string += '\n-------- STDERR ----------\n'
    string += str(stderr) +'\n'
    return string


def get_service_ip(service, instance):
    ''' Get the IP address of a given service'''
    
    # Do not use .format as there are too many graph brackets    
    IP = shell('docker inspect --format \'{{ .NetworkSettings.IPAddress }}\' ' + PROJECT_NAME + '-' + service + '-' +instance, capture=True).stdout
    
    if IP:
        try:
            socket.inet_aton(IP)
        except socket.error:
            raise Exception('Error, I could not find a valid IP address for service "{}", instance "{}"'.format(service, instance))
            
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
    '''Get DockerOps version'''
    
    last_commit_info = shell('cd ' + os.getcwd() + ' && git log | head -n3', capture=True).stdout
    if not last_commit_info:
        print('\nDockerOps v0.6.2-pre')
    else:
        print('\nDockerOps v0.6.2-pre')
        last_commit_info_lines = last_commit_info.split('\n')
        commit_shorthash = last_commit_info_lines[0].split(' ')[1][0:7]
        commit_date      = last_commit_info_lines[-1].replace('  ', '')
        print('Current repository commit: {}'.format(commit_shorthash))
        print(commit_date)
    
        python_version = shell('python -V', capture=True)
        
        if python_version.stdout:
            print('Python version: {}'.format(python_version.stdout))
        if python_version.stderr:
            print('Python version: {}'.format(python_version.stderr))

@task
def install_demo():
    '''install the DockerOps demo in a directory named 'dockerops-demo' in the current path'''
    
    INSTALL_DIR = PROJECT_DIR
    
    print('\nInstalling DockerOps demo in current directory ({})...'.format(INSTALL_DIR))
    import shutil

    try:
        shutil.copytree(os.getcwd()+'/demo', INSTALL_DIR + '/dockerops-demo')
    except OSError as e:
        abort('Could not copy demo data into {}: {}'.format(INSTALL_DIR + '/services', e))
        
    print('\nDemo installed.')
    print('\nQuickstart: enter into "{}", then:'.format(INSTALL_DIR))
    print('  - to build it, type "dockerops build:all";')
    print('  - to run it, type "dockerops run:all";')
    print('  - to see running services, type "dockerops ps";')
    print('  - to ssh into the "demo", instance "two" service, type "dockerops ssh:demo,instance=two";')
    print('    - to ping service "demo", instance "one", type: "ping demo-one";')
    print('    - to exit ssh type "exit";')
    print('  - to stop the demo, type "dockerops clean:all".')


#--------------------------
# Services management
#--------------------------

@task
def init(os_to_init='ubuntu14.04', verbose=False):
    '''Initialize the base services'''
    
    # Sanity checks:
    if os_to_init not in SUPPORTED_OSES:
        abort('Sorry, unsupported OS. Got "{}" while supported OSes are: {}'.format(os_to_init, SUPPORTED_OSES))
    
    # Switches
    os_to_init  = os_to_init
    verbose     = booleanize(verbose=verbose)
    
    # Build base images
    build(service='dockerops-common-{}'.format(os_to_init), verbose=verbose, nocache=False)
    build(service='dockerops-base-{}'.format(os_to_init), verbose=verbose, nocache=False)

    # If DockerOps DNS service does not exist, build and use this one
    if shell('docker inspect dockerops/dockerops-dns', capture=True).exit_code != 0:
        build(service='dockerops-dns-{}'.format(os_to_init), verbose=verbose, nocache=False)
        shell('docker tag dockerops/dockerops-dns-{} dockerops/dockerops-dns'.format(os_to_init))


@task
def build(service=None, verbose=False, nocache=False):
    '''Build a given service. If service name is set to "all" then builds all the services'''

    # Sanitize...
    (service, _) = sanity_checks(service)

    # Switches
    verbose  = booleanize(verbose=verbose)
    
    # Backcomp #TODO: remove 'verbose'
    if verbose:
        verbose = True
    
    if service.upper()=='ALL':

        # Build everything then obtain which services we have to build        
        print('\nBuilding all services in {}'.format(SERVICES_IMAGES_DIR))


        # Find dependencies recursive function
        def find_dependencies(service_dir):
            with open(SERVICES_IMAGES_DIR+'/'+service_dir+'/Dockerfile') as f:
                content = f.read()
                for line in content.split('\n'):
                    if line.startswith('FROM '):
                        from_service = line.split(' ')[1]
                        if '/' in from_service:   
                            from_service_project = from_service.split('/')[0]
                            from_service_app = from_service.split('/')[1]
                            if from_service_project.lower() == PROJECT_NAME:                  
                                return [from_service_app] + find_dependencies(from_service_app)                            
                            else:
                                return []

        # Find build hierarchy
        built = []
        for service_dir in os.listdir(SERVICES_IMAGES_DIR):
            if not os.path.isdir(SERVICES_IMAGES_DIR+'/'+service_dir):
                continue
            if service_dir in built:
                logger.debug('%s already built',service_dir)
                continue
            logger.debug('Processing %s',service_dir)
            try:
                dependencies = find_dependencies(service_dir)
                if dependencies:
                    logger.debug('Service %s depends on: %s',service_dir, dependencies)
                    dependencies.reverse()
                    logger.debug('Dependencies build order: %s', dependencies) 
                    for service in dependencies:
                        if service not in built:
                            # Build by recursively call myself
                            build(service=service, verbose=verbose)
                            built.append(service)
                build(service=service_dir, verbose=verbose)
                    
            except IOError:
                pass

    else:
        # Build a given service
        service_dir = get_service_dir(service)

        # Obtain the base image
        with open('{}/Dockerfile'.format(service_dir)) as f:
            content = f.read()

        image = None
        for line in content.split('\n'):
            if line.startswith('FROM'):
                image = line.strip().split(' ')[-1]

        if not image:
            abort('Missing "FROM" in Dockerfile?!')

        # If dockerops's 'FROM' images does not existe, build them
        if image.startswith('dockerops/'):
            logger.debug('Checking image "{}"...'.format(image))
            if shell('docker inspect {}'.format(image), capture=True).exit_code != 0:
                logger.info('Could not find image "{}", now building it...'.format(image))
                build(service=image.split('/')[1], verbose=verbose, nocache=False)

                # If we built a base and no DNS is yet present, buid it as well
                if image in ['dockerops/dockerops-base-ubuntu14.04']: #TODO: support 16.04 as well
                    if shell('docker inspect dockerops/dockerops-dns', capture=True).exit_code != 0:
                        logger.info('Building DNS as well...')
                        build(service='dockerops-dns-ubuntu14.04', verbose=verbose, nocache=False)
                        shell('docker tag dockerops/dockerops-dns-ubuntu14.04 dockerops/dockerops-dns')
                    else:
                        logger.debgu('DNS alredy present, not building it...')
            else:
                logger.debug('Found image "{}"'.format(image))

        # Default tag prefix to PROJECT_NAME    
        tag_prefix = PROJECT_NAME
        
        # But if we are running a DockerOps service, use DockerOps image
        if is_base_service(service):
            tag_prefix = 'dockerops'

        # Ok, print the info about the service being built
        print('\nBuilding service "{}" as "{}/{}"'.format(service, tag_prefix, service))

        # Check that only a prestartup script is found:
        prestartup_scripts = [f for f in os.listdir(service_dir) if re.match(r'prestartup_+.*\.sh', f)]
        if len(prestartup_scripts) > 1:
            abort("Sorry, found more than one prestartup script for this service an this is not allowed (got {})".format(prestartup_scripts))

        # Update prestartup script date to allow ordered execution
        if prestartup_scripts:
            shell('touch {}/{}'.format(service_dir, prestartup_scripts[0]),silent=True)
 
        # Build command 
        if nocache:
            print('Building without cache')
            build_command = 'cd ' + service_dir + '/.. &&' + 'docker build --no-cache -t ' + tag_prefix +'/' + service + ' ' + service
        else:
            print('Building with cache')
            build_command = 'cd ' + service_dir + '/.. &&' + 'docker build -t ' + tag_prefix +'/' + service + ' ' + service
        
        # Build
        print('Building...')
        if verbose:
            shell(build_command, verbose=True)
        else:
            if shell(build_command, verbose=False, capture=False, silent=True):
                print('Build OK')
            else:
                abort('Something happened')



@task
def start(service,instance):
    '''Start a stopped service. Use only if you know what you are doing.''' 
    if service_exits_but_not_running(service,instance):
        shell('docker start {}-{}'.format(service,instance), silent=True)
    else:
        abort('Cannot start a service not in exited state. use "run" instead')

@task
def rerun(service, instance=None):
    '''Re-run a given service (instance is not mandatory if only one is running)'''
    running_instances = get_running_services_instances_matching(service)
    if len(running_instances) == 0:
        abort('Could not find any running instance of service matching "{}"'.format(service))                
    if len(running_instances) > 1:
        abort('Found more than one running instance for service "{}": {}, please specity wich one.'.format(service, running_instances))            
    service = running_instances[0][0]
    instance  = running_instances[0][1]

    # Clean    
    clean(service,instance)
    run(service,instance,from_rerun=True)

@task
# TODO: clarify difference between False and None.
def run(service=None, instance=None, group=None, instance_type=None,
        persistent_data=None, persistent_opt=None, persistent_log=None,
        publish_ports=None, linked=None, seed_command=None, conf=None,
        safemode=None,  interactive=None, recursive=False, from_rerun=False, nethost=None):
    '''Run a given service with a given instance. If no instance name is set,
    a standard instance with a random name is run. If service name is set to "all"
    then all the services are run, according  to the run conf file.'''

    #------------------------
    # Handle conf(s)
    #------------------------

    # Load host conf 
    host_conf = load_host_conf()
    
    # Handle last run conf
    try:
        last_conf = host_conf['last_conf']
        if not conf:
            conf = last_conf
    except KeyError:
        if conf:
            host_conf['last_conf'] = conf
            save_host_conf(host_conf)
    else:
        if last_conf != conf:
            host_conf['last_conf'] = conf
            save_host_conf(host_conf)

    print('')
    if not recursive:
        print('Conf file being used: "{}"'.format('run.conf' if not conf else conf))
    
    #---------------------------
    # Run a group of services
    #---------------------------
    if service == 'all' or group:
        
        if service == 'all':
            #print('WARNING: using the magic keyword "all" is probably going to be deprecated, use group=all instead.')
            group = 'all'
        
        print('Running services in {} for group {}'.format(SERVICES_IMAGES_DIR,group))

        if safemode or interactive:
            abort('Sorry, you cannot set one of the "safemode" or "interactive" switches if you are running more than one service') 



        # Load run conf             
        try:
            services_to_run_confs = get_services_run_conf(conf)
        except Exception as e:
            abort('Got error in reading run conf for automated execution: {}.'.format(e))

        if not services_to_run_confs:
            abort('No or empty run.conf found in {}, are you in the project\'s root?'.format(SERVICES_IMAGES_DIR))
        
        for service_conf in services_to_run_confs:
            
            # Check for service group.
            # We will run the service if:
            # a) the group is set to 'all'
            # b) the group is set to 'x' and the service group is 'x'            
            if group != 'all':
                if 'group' in service_conf:
                    if service_conf['group'] != group:
                        continue
                else:
                    continue
                
            # Check for service name
            if 'service' not in service_conf:
                abort('Missing service name for conf: {}'.format(service_conf))
            else:
                service = service_conf['service']
              
            # Check for instance name
            if 'instance' not in service_conf:
                abort('Missing instance name for conf: {}'.format(service_conf))
            else:
                instance = service_conf['instance']

            # Handle the instance type.
            if 'instance_type' in service_conf:
                    instance_type = service_conf['instance_type']
            else:
                instance_type = None

            # Recursively call myself with proper args. The args of the call always win over the configuration(s)
            run(service         = service,
                instance        = instance,
                instance_type   = instance_type,
                persistent_data = persistent_data if persistent_data is not None else (service_conf['persistent_data'] if 'persistent_data' in service_conf else None),
                persistent_log  = persistent_log  if persistent_log  is not None else (service_conf['persistent_log']  if 'persistent_log'  in service_conf else None),
                persistent_opt  = persistent_opt  if persistent_opt  is not None else (service_conf['persistent_opt']  if 'persistent_opt'  in service_conf else None),
                publish_ports   = publish_ports   if publish_ports   is not None else (service_conf['publish_ports']   if 'publish_ports'   in service_conf else None),
                linked          = linked          if linked          is not None else (service_conf['linked']          if 'linked'          in service_conf else None),
                interactive     = interactive,
                safemode        = safemode,
                conf            = conf,
                recursive       = True)
                
        # Exit
        return

    #-----------------------
    # Run a given service
    #-----------------------
    
    # Sanitize...
    (service, instance) = sanity_checks(service, instance)

    # Run a specific service
    print('Running service "{}" ("{}/{}"), instance "{}"...'.format(service, PROJECT_NAME, service, instance))

    # Check if this service is exited
    if service_exits_but_not_running(service,instance):

        if interactive:
            # Only for instances run in interactive mode we take the right of cleaning
            shell('fab clean:{},instance=safemode'.format(service), silent=True)

        abort('Service "{0}", instance "{1}" exists but it is not running, I cannot start it since the linking ' \
              'would be end up broken. Use dockerops clean:{0},instance={1} to clean it and start over clean, ' \
              'or dockerops start:{0},instance={1} if you know what you are doing.'.format(service,instance))

    # Check if this service is already running
    if is_service_running(service,instance):
        print('Service is already running, not starting.')
        # Exit
        return    

    # Init service conf and requested env vars
    service_conf = None
    ENV_VARs       = {}

    # Add to the ENV_VARs the ones specified in the required.env_vars.json file
    for env_var in get_required_env_vars(service):
        ENV_VARs[env_var] = None

    # Check if this service is listed in the run conf:
    if is_service_registered(service, conf):
        
        # If the service is registered, the the rules of the run conf applies, so:

        # 1) Read the conf if any
        try:
            services_to_run_confs = get_services_run_conf(conf)
        except Exception as e:
            abort('Got error in reading run conf for loading service info: {}.'.format(e))        
    
        for item in services_to_run_confs:
            # The configuration for a given service is ALWAYS applied.
            # TODO: Allow to have different confs per different instances? Could be useful for linking a node with a given server. 
            # i.e. node instance A with server instance A, node instance B with server instance B.
            if instance:
                if (service == item['service'] and instance == item['instance']):
                    logger.debug('Found conf for service "%s", instance "%s"', service, instance)
                    service_conf = item
            else:
                if (service == item['service']):
                    logger.debug('Found conf for service "%s"', service)
                    service_conf = item
        if not service_conf:
            conf_file = conf if conf else 'default (run.conf)'
            if not confirm('WARNING: Could not find conf for service {}, instance {} in the {} conf file. Should I proceed?'.format(service, instance, conf_file)):
                return
        
        # 2) Handle the instance type.
        if service_conf and not instance_type:
            if 'instance_type' in service_conf:
                if service_conf['instance_type'] in ['standard', 'published', 'persistent', 'master']:
                    instance_type = service_conf['instance_type']
                else:
                    abort('Unknown or unapplicable instance type "{}"'.format(instance_type))
            else:
                if service_conf['instance'] in ['standard', 'published', 'persistent', 'master', 'debug']:
                    instance_type = service_conf['instance']
                else:
                    instance_type = 'standard'
                                          
        # 3) Now, enumerate the vars required by this service:
        if service_conf and 'env_vars' in service_conf:     
            for env_var in service_conf['env_vars']:
                ENV_VARs[env_var] = service_conf['env_vars'][env_var]

    # Set emptu service_conf dict to avoid looking up in a None object
    if not isinstance(service_conf,dict):
        service_conf={}
 
    # Handle the instance type.
    if 'instance_type' in service_conf:
            instance_type = service_conf['instance_type']
    else:
        instance_type = None

    persistent_data = persistent_data if persistent_data is not None else (service_conf['persistent_data'] if 'persistent_data' in service_conf else None)
    persistent_log  = persistent_log  if persistent_log  is not None else (service_conf['persistent_log']  if 'persistent_log'  in service_conf else None)
    persistent_opt  = persistent_opt  if persistent_opt  is not None else (service_conf['persistent_opt']  if 'persistent_opt'  in service_conf else None)
    publish_ports   = publish_ports   if publish_ports   is not None else (service_conf['publish_ports']   if 'publish_ports'   in service_conf else None)
    linked          = linked          if linked          is not None else (service_conf['linked']          if 'linked'          in service_conf else None)               
    nethost         = nethost         if nethost         is not None else (service_conf['nethost']         if 'nethost'         in service_conf else None)


    # Handle instance type for not regitered services of if not set:
    if not instance_type:
        if instance in ['standard', 'published', 'persistent', 'master', 'debug']:
            instance_type = instance
        else:
            instance_type = 'standard'

    print('Instance type set to "{}"'.format(instance_type))

    # Set switches (command line values have always the precedence)
    linked          = setswitch(linked=linked, instance_type=instance_type)
    persistent_data = setswitch(persistent_data=persistent_data, instance_type=instance_type)
    persistent_log  = setswitch(persistent_log=persistent_log, instance_type=instance_type)
    persistent_opt  = setswitch(persistent_opt=persistent_opt, instance_type=instance_type)
    publish_ports   = setswitch(publish_ports=publish_ports, instance_type=instance_type)
    interactive     = setswitch(interactive=interactive, instance_type=instance_type)
    safemode        = setswitch(safemode=safemode, instance_type=instance_type)

    # Now add the always present env vars
    ENV_VARs['SERVICE']         = service
    ENV_VARs['INSTANCE']        = instance
    ENV_VARs['INSTANCE_TYPE']   = instance_type
    ENV_VARs['PERSISTENT_DATA'] = persistent_data
    ENV_VARs['PERSISTENT_LOG']  = persistent_log
    ENV_VARs['PERSISTENT_OPT']  = persistent_opt
    ENV_VARs['SAFEMODE']        = safemode
    ENV_VARs['HOST_HOSTNAME']   = socket.gethostname()
            
    # Start building run command
    if nethost:
        run_cmd = 'docker run --name {}-{}-{} --net host'.format(PROJECT_NAME, service,instance)
    else:
        run_cmd = 'docker run --name {}-{}-{} '.format(PROJECT_NAME, service,instance)

    # Handle linking...
    if linked:
        if service_conf and 'links' in service_conf:
            for link in service_conf['links']:

                if not link:
                    continue
              
                # Handle link shortcut
                if isinstance(link, str) or isinstance(link, unicode):
                    
                    if (not '-' in link) or (not ':' in link):
                        abort('Wrong link shortcut string format, cannot find dash or column. See doc.')
                    
                    link_pieces = link.split(':')[0].split('-')
                    
                    # Shortcuts
                    link_name      = link.split(':')[1]
                    link_service = '-'.join(link_pieces[:-1])
                    link_instance  = link_pieces[-1]         
                
                elif isinstance(link, dict):
                    if 'name' not in link:
                        abort('Sorry, you need to give me a link name (ore use the string shortcut for defining it)')
                    if 'service' not in link:
                        abort('Sorry, you need to give me a link service (ore use the string shortcut for defining it)')
                    if 'instance' not in link:
                        abort('Sorry, you need to give me a link instance (ore use the string shortcut for defining it)')
                    
                    # Shortcuts
                    link_name      = link['name']
                    link_service = link['service']
                    link_instance  = link['instance']
                else:
                    abort('Sorry, link must be defining using a dict or a string shortcut (see doc), got {}'.format(link.__class__.__name__))

                
                running_instances = get_running_services_instances_matching(service)
                
                # Validate: detect if there is a running service for link['service'], link['instance']

                # Obtain any running instances. If link_instance is None, finds all running instances for service and
                # warns if more than one instance is found.
                running_instances = get_running_services_instances_matching(link_service, link_instance)         
                
                if len(running_instances) == 0:
                    logger.info('Could not find any running instance of service matching "{}" which is required for linking by service "{}", instance "{}". I will expect an env var for proper linking setup'.format(link_service, service, instance))             
                    ENV_VARs[link_name.upper()+'_SERVICE_IP'] = None
                    
                else:
                    if len(running_instances) > 1:
                        logger.warning('Found more than one running instance for service "{}" which is required for linking: {}. I will use the first one ({}). You can set explicity on which instance to link on in run.conf'.format(link_service, running_instances, running_instances[0]))
                      
                    link_service = running_instances[0][0]
                    link_instance  = running_instances[0][1]
    
                    # Now add linking flag for this link
                    run_cmd += ' --link {}:{}'.format(PROJECT_NAME+'-'+link_service+'-'+link_instance, link_name)
                    
                    # Also, add an env var with the linked service IP
                    ENV_VARs[link_name.upper()+'_SERVICE_IP'] = get_service_ip(link_service, link_instance)


    # If instance has publish_ports enabld (also for master and published) then check
    # that SERVICE_IP is set (and if not, warn)
    if publish_ports and not 'SERVICE_IP' in ENV_VARs:
        if instance_type == 'master':
            abort('SERVICE_IP env var is required when running in master mode')
        elif service == 'dockerops-dns':
            abort('SERVICE_IP env var is required when publishing the dockerops-dns service')            
        else:
            logger.warning('You are publishing the service but you have not set the SERVICE_IP env var. This mean that the service(s) might not be completely accessible outside the Docker network.')

    # Try to set the env vars from the env (they have always the precedence):
    for requested_ENV_VAR in ENV_VARs.keys():
        requested_ENV_VAR_env_value = os.getenv(requested_ENV_VAR, None)
        if requested_ENV_VAR_env_value:
            logger.debug('Found env var %s with value "%s"', requested_ENV_VAR, requested_ENV_VAR_env_value)
            
            if ENV_VARs[requested_ENV_VAR] is not None:
                print('WARNING: I am overriding atomaticaly set env var {} (value="{}") and I will use value "{}" as I found it in the env'.format(requested_ENV_VAR, ENV_VARs[requested_ENV_VAR], requested_ENV_VAR_env_value))

            ENV_VARs[requested_ENV_VAR] = requested_ENV_VAR_env_value


    # Check that we have all the required env vars. Do NOT move this section around, it has to stay here.
    if None in ENV_VARs.values():
        logger.debug('After checking the env I still cannot find some required env vars, proceeding with the host conf')

        for requested_ENV_VAR in ENV_VARs:
            
            if ENV_VARs[requested_ENV_VAR] is None:
                
                logger.debug('Evaluating required ENV_VAR %s', requested_ENV_VAR)
                
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
                        save_host_conf(host_conf)

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
        logger.debug('Done applying functions to ENV vars. New summary: %s', ENV_VARs)

    # Handle persistency
    if persistent_data or persistent_log or persistent_opt:

        # Check project data dir exists:
        if not os.path.exists(DATA_DIR):
            if not confirm('WARNING: You are running with persistency enabled but I cannot find the data directory "{}". If this is the first time you are runnign the project with persitsency enabled, this is fine. Otherwise, you might want to check you configuration. Proceed?'.format(DATA_DIR)):
                abort('Exiting...')             
            os.makedirs(DATA_DIR)
            
        # Check service instance dir exists:
        service_instance_dir = DATA_DIR + '/' + service + '-' + instance
        if not os.path.exists(service_instance_dir):
            logger.debug('Data dir for service instance not existent, creating it.. ({})'.format(service_instance_dir))
            os.mkdir(service_instance_dir)
        
        # Now mount the dir in /persistent in the Docker: here we just provide a persistent storage in the Docker service.
        # the handling of data, opt and log is done in the Dockerfile.
        run_cmd += ' -v {}:/persistent'.format(service_instance_dir)    

    # Handle extra volumes
    if service_conf and 'volumes' in service_conf:
        volumes = service_conf['volumes'].split(',')
        for volume in volumes:
            run_cmd += ' -v {}'.format(volume)

    # Handle published ports
    if publish_ports:

        # Obtain the ports to publish from the Dockerfile
        try:
            with open(get_service_dir(service)+'/Dockerfile') as f:
                content = f.readlines()
        except IOError:
            abort('No Dockerfile found (?!) I was looking in {}'.format(get_service_dir(service)+'/Dockerfile'))
        
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
                            abort('Got unknown port from service\'s dockerfile: "{}"'.format(port))

            if line.startswith('#UDP_EXPOSE'):
                # Clean up the line
                line_clean =  line.replace('\n','').replace(' ',',').replace('#UDP_EXPOSE','')
                for port in line_clean.split(','):
                    if port:
                        try:
                            # Append while validating
                            udp_ports.append(int(port))
                        except ValueError:
                            abort('Got unknown port from service\'s dockerfile: "{}"'.format(port))

        # Handle forcing of an IP where to publish the ports
        if 'PUBLISH_ON_IP' in ENV_VARs:
            pubish_on_ip = ENV_VARs['PUBLISH_ON_IP']+':'
        elif 'SERVICE_IP' in ENV_VARs:
            pubish_on_ip = ENV_VARs['SERVICE_IP']+':'
        else:
            pubish_on_ip = ''

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

    # If OSX, expose ssh on a different port
    if running_on_osx():
        from random import randint

        while True:

            # Get a random ephimeral port
            port = randint(49152, 65535)

            # Check port is available
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', port))
            if result == 0:
                logger.info('Found not available ephimeral port ({}) , choosing another one...'.format(port))
                import time
                time.sleep(1)
            else:
                break

        run_cmd += ' -p {}:22'.format(port)


    # Add env vars..
    logger.debug("Adding env vars: %s", ENV_VARs)
    for ENV_VAR in ENV_VARs:  
        # TODO: all vars are understood as strings. Why?  
        if isinstance(ENV_VAR, bool) or isinstance(ENV_VAR, float) or isinstance(ENV_VAR, int):
            run_cmd += ' -e {}={}'.format(ENV_VAR, ENV_VARs[ENV_VAR])
        else:
            run_cmd += ' -e {}="{}"'.format(ENV_VAR, str(ENV_VARs[ENV_VAR]))

    # Handle hostname
    if not nethost:
        if service_conf and 'hostname' in service_conf:
            run_cmd += ' -h {}'.format(service_conf['hostname'])
        else:
            run_cmd += ' -h {}-{}'.format(service,instance)

    # Set seed command
    if not seed_command:
        if interactive:
            seed_command = 'bash'
        else:
            seed_command = 'supervisord'

    # Default tag prefix to PROJECT_NAME    
    tag_prefix = PROJECT_NAME

    # But if we are running a DockerOps service, use DockerOps image
    if is_base_service(service):
        tag_prefix = 'dockerops'

    if interactive:
        run_cmd += ' -i -t {}/{}:latest {}'.format(tag_prefix, service, seed_command)
        local(run_cmd)
        shell('fab clean:service={},instance={}'.format(service,instance), silent=True)
        
    else:
        run_cmd += ' -d -t {}/{}:latest {}'.format(tag_prefix, service, seed_command)   
        if not shell(run_cmd, silent=True):
            abort('Something failed')
        print('Done.')
   
    # In the end, the sleep..
    if service_conf and 'sleep' in service_conf:
        if not interactive and not from_rerun:
            to_sleep = int(service_conf['sleep'])
            if to_sleep:
                print('Now sleeping {} seconds to allow service setup...'.format(to_sleep))
                sleep(to_sleep)
 
    
    
@task
def clean(service=None, instance=None, group=None, force=False, conf=None):
    '''Clean a given service. If service name is set to "all" then clean all the services according 
    to the run conf file. If service name is set to "reallyall" then all services on the host are cleaned'''

    # all: list services to clean (check run conf first)
    # reallyall: warn and clean all
    
    if service == 'reallyall':
        
        print('')
        if confirm('Clean all services? WARNING: this will stop and remove *really all* Docker services running on this host!'):
            print('Cleaning all Docker services on the host...')
            shell('docker stop $(docker ps -a -q) &> /dev/null', silent=True)
            shell('docker rm $(docker ps -a -q) &> /dev/null', silent=True)

    elif service == 'all' or group:
        
        # Check conf
        try:
            last_conf = load_host_conf()['last_conf']
        except KeyError:
            last_conf= None
        
        if last_conf:
            if conf:
                if conf != last_conf:
                    if not confirm('You specificed the conf file "{}" while the last conf used is "{}". Are you sure to proceed?'.format(conf, last_conf)):
                        abort('Exiting...')
            else:
                conf = last_conf
                
        print('\nConf file being used: "{}"'.format('run.conf' if not conf else conf))

        if service == 'all':
            #print('WARNING: using the magic keyword "all" is probably going to be deprecated, use group=all instead.')
            group = 'all'        

        # Get service list to clean
        one_in_conf = False
        services_run_conf = []
        for service_conf in get_services_run_conf(conf):
            
            # Do not clean instances not explicity set in run.conf (TODO: do we want this?)
            if not service_conf['instance']:
                continue
            
            # Do not clean instances not belonging to the group we want to clean
            if group != 'all' and 'group' in service_conf and service_conf['group'] != group:
                continue
            
            # Understand if the service to clean is running
            if is_service_running(service=service_conf['service'], instance=service_conf['instance']) \
              or service_exits_but_not_running(service=service_conf['service'], instance=service_conf['instance']):
                if not one_in_conf:
                    print('\nThis action will clean the following services instances according to run conf:')
                    one_in_conf =True  
                print(' - service "{}" ("{}/{}"), instance "{}"'.format(service_conf['service'], PROJECT_NAME, service_conf['service'], service_conf['instance']))
                services_run_conf.append({'service':service_conf['service'], 'instance':service_conf['instance']})

        # Understand if There is more
        more_runnign_services_conf = []
        
        for item in ps(capture=True):
            # TODO: let ps return a list of namedtuples..
            service = item[-1].split(',')[0]
            instance  = item[-1].split('=')[1]
            registered = False
            for service_conf in services_run_conf:
                if service == service_conf['service'] and instance == service_conf['instance']:
                    registered = True
            if not registered:
                more_runnign_services_conf.append({'service':service, 'instance':instance})
                
        if one_in_conf and more_runnign_services_conf:
            print('\nMoreover, the following services instances will be clean as well as part of this project:')
        elif more_runnign_services_conf:
            print('\nThe following services instances will be clean as part of this project:')
        else:
            pass

        for service_conf in more_runnign_services_conf:
            print(' - service "{}" ("{}/{}"), instance "{}"'.format(service_conf['service'], PROJECT_NAME, service_conf['service'], service_conf['instance']))
        
        # Sum the two lists
        services_to_clean_conf = services_run_conf + more_runnign_services_conf
        
        if not services_to_clean_conf:
            print('\nNothing to clean, exiting..')
            return
        print('')
        if force or confirm('Proceed?'):
            for service_conf in services_to_clean_conf:
                if not service_conf['instance']:
                    print('WARNING: I Cannot clean {}, instance='.format(service_conf['service'], service_conf['instance']))
                else:
                    print('Cleaning service "{}", instance "{}"..'.format(service_conf['service'], service_conf['instance']))          
                    shell("docker stop "+PROJECT_NAME+"-"+service_conf['service']+"-"+service_conf['instance']+" &> /dev/null", silent=True)
                    shell("docker rm "+PROJECT_NAME+"-"+service_conf['service']+"-"+service_conf['instance']+" &> /dev/null", silent=True)
                            
    else:
        
        # Check conf
        try:
            last_conf = load_host_conf()['last_conf']
        except KeyError:
            last_conf= None
        
        if last_conf:
            if conf:
                if conf != last_conf:
                    if not confirm('You specificed the conf file "{}" while the last conf used is "{}". Are you sure to proceed?'.format(conf, last_conf)):
                        abort('Exiting...')
            else:
                conf = last_conf
                
        print('\nConf file being used: "{}"'.format('run.conf' if not conf else conf))

        # Sanitize (and dynamically obtain instance)...
        (service, instance) = sanity_checks(service,instance)
        
        if not instance:
            print('I did not find any running instance to clean, exiting. Please note that if the instance is not running, you have to specify the instance name to let it be clened')
        else:
            print('Cleaning service "{}", instance "{}"..'.format(service,instance))   
            shell("docker stop "+PROJECT_NAME+"-"+service+"-"+instance+" &> /dev/null", silent=True)
            shell("docker rm "+PROJECT_NAME+"-"+service+"-"+instance+" &> /dev/null", silent=True)
                            
        
    

@task
def ssh(service=None, instance=None):
    '''SSH into a given service'''
    
    # Sanitize...
    (service, instance) = sanity_checks(service,instance)
    
    try:
        IP = get_service_ip(service, instance)
    except Exception as e:
        abort('Got error when obtaining IP address for service "{}", instance "{}": "{}"'.format(service,instance, e))
    if not IP:
        abort('Got no IP address for service "{}", instance "{}"'.format(service,instance))

    # Check if the key has proper permissions
    if not shell('ls -l keys/id_rsa',capture=True).stdout.endswith('------'):
        shell('chmod 600 keys/id_rsa', silent=True)

    # Workaround for bug in OSX
    # See https://github.com/docker/docker/issues/22753
    if running_on_osx():
        # Get container ID
        info = shell('dockerops info:{},{}'.format(service,instance),capture=True).stdout.split('\n')
        container_id = info[2].split(' ')[0]

        # Get inspect data
        inspect = json.loads(shell('docker inspect {}'.format(container_id),capture=True).stdout)

        # Check that we are operating on the right container
        if not inspect[0]['Id'].startswith(container_id):
            abort('DockerOps intenral error (containers ID do not match)')

        # Get host's port for SSH
        port = inspect[0]['NetworkSettings']['Ports']['22/tcp'][0]['HostPort']

        # Call SSH on the right (host's) port
        shell(command='ssh -p {} -oStrictHostKeyChecking=no -i keys/id_rsa dockerops@127.0.0.1'.format(port), interactive=True)

    else:
        shell(command='ssh -oStrictHostKeyChecking=no -i keys/id_rsa dockerops@' + IP, interactive=True)

@task
def help():
    '''Show this help'''
    shell('fab --list', capture=False)

@task
def get_ip(service=None, instance=None):
    '''Get a service IP'''

    # Sanitize...
    (service, instance) = sanity_checks(service,instance)
    
    # Get running instances
    running_instances = get_running_services_instances_matching(service)
    # For each instance found print the ip address
    for i in running_instances:
        print('IP address for {} {}: {}'.format(i[0], i[1], get_service_ip(i[0], i[1])))

# TODO: split in function plus task, allstates goes in the function

@task
def info(service=None, instance=None, capture=False):
    '''Obtain info about a given service'''
    return ps(service=service, instance=instance, capture=capture, info=True)

@task
def ps(service=None, instance=None, capture=False, onlyrunning=False, info=False, conf=None):
    '''Info on running services. Give a service name to obtain informations only about that specific service.
    Use the magic words 'all' to list also the not running ones, and 'reallyall' to list also the services not managed by
    DockerOps (both running and not running)'''

    # TODO: this function has to be COMPLETELY refactored. Please do not look at this code.
    # TODO: return a list of namedtuples instead of a list of lists

    known_services_fullnames          = None

    if not service:
        service = 'project'

    if not info and service not in ['all', 'platform', 'project', 'reallyall']:
        abort('Sorry, I do not understand the command "{}"'.format(service))

    if service == 'platform':
        known_services_fullnames = [conf['service']+'-'+conf['instancef'] for conf in get_services_run_conf(conf)]
        
    # Handle magic words all and reallyall
    if onlyrunning: # in ['all', 'reallyall']:
        out = shell('docker ps', capture=True)
        
    else:
        out = shell('docker ps -a', capture=True)
    
    # If error:
    if out.exit_code != 0:
        print(format_shell_error(out.stdout, out.stderr, out.exit_code))

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
                    
                    # Obtain service_name_position
                    if item == 'NAMES':
                        service_name_position = count
                        
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
                           
            if len(line_content) == 6:
                line_content.append(line_content[5])
                line_content[5] = None

            

            # Convert service names
            for i, item in enumerate(line_content):
                
                if i == image_name_position:
                    image_name = item
                    
                if i == service_name_position:

                    # Set service name
                    service_name = item

                    # Filtering against defined dockers
                    # If a service name was given, filter against it:
                    if service and not service in ['all', 'platform', 'project', 'reallyall']:
                        
                        # Here we are filtering
                        if service[-1] == '*':
                            if service_name.startswith(PROJECT_NAME+'-'+service[0:-1]):
                                if instance and not service_name.endswith('-'+instance):
                                    continue
                            else:
                                continue
                        else:
                            if service_name.startswith(PROJECT_NAME+'-'+service+'-'):
                                if instance and not service_name.endswith('-'+instance):
                                    continue
                            else:
                                continue
                        
                    if instance:
                        if service_name.endswith('-'+instance):
                            pass
                        else: 
                            continue
 
                    # Handle Dockerops services service
                    if ('-' in service_name) and (not service == 'reallyall') and (service_name.startswith(PROJECT_NAME+'-')):
                        if known_services_fullnames is not None:
                            # Filter against known_services_fullnames
                            if service_name not in known_services_fullnames:
                                logger.info('Skipping service "{}" as it is not recognized by DockerOps. Use the "all" magic word to list them'.format(service_name))
                                continue
                            else:
                                
                                # Remove project name:
                                if not service_name.startswith(PROJECT_NAME):
                                    raise Exception('Error: this service ("{}") is not part of this project ("{}")?!'.format(service_name, PROJECT_NAME))
                                service_name = service_name[len(PROJECT_NAME)+1:]    
                                
                                # Add it 
                                service_instance = service_name.split('-')[-1]
                                service_name = '-'.join(service_name.split('-')[0:-1]) + ',instance='+str(service_instance)
                                line_content[service_name_position] = service_name
                                content.append(line_content)    
                                
                        else:
                            
                            # Remove project name:
                            if not service_name.startswith(PROJECT_NAME):
                                raise Exception('Error: this service ("{}") is not part of this project ("{}")?!'.format(service_name, PROJECT_NAME))
                            service_name = service_name[len(PROJECT_NAME)+1:]
                            
                            # Add it
                            service_instance = service_name.split('-')[-1]
                            service_name = '-'.join(service_name.split('-')[0:-1]) + ',instance='+str(service_instance)
                            line_content[service_name_position] = service_name
                            content.append(line_content)
                            
                    # Handle non-Dockerops services 
                    else:
                        if service=='reallyall': 
                            line_content[service_name_position] = service_name
                            content.append(line_content)
                        else:
                            continue
  
    #-------------------
    # Print output
    #-------------------
    if not capture:
        print('')
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
                print('  {}'.format(item), end=' ')
                # How many spaces?
                spaces = max_lenghts[cursor] - len(item)
                
                if spaces>0:
                    for _ in range(spaces):
                        print(' ', end='')
    
                cursor+=1
        print('')
        
        # Print List 
        for entry in content:
            cursor=0
            for i, item in enumerate(entry):
                if i in positions:
                    print('  {}'.format(item), end=' ')
                    # How many spaces?
                    spaces = max_lenghts[cursor] - len(item)
                    
                    if spaces>0:
                        for _ in range(spaces):
                            print(' ', end='')
        
                    cursor+=1
            print('')
    
        # Print output and stderr if any
        if out.stderr:
            print(out.stderr)
        
    else:
        return content

















