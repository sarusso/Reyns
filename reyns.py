#--------------------------
# Imports
#--------------------------
from __future__ import print_function

import os
import sys
import inspect
import uuid
import logging
import json
import socket
try:
    import fcntl
except ImportError:
    fcntl = None
import struct
import platform
import re
import subprocess
from collections import namedtuple
from time import sleep


#--------------------------
# Platform detection
#--------------------------

# Are we running on OSX?
def running_on_osx():
    if platform.system().upper() == 'DARWIN':
        return True
    else:
        return False

# Are we running on Windows?
def running_on_windows():
    if platform.system().upper() == 'WINDOWS':
        return True
    else:
        return False


def running_on_unix():
    if not running_on_windows() and not running_on_osx():
        return True

#--------------------------
# Conf
#--------------------------

PROJECT_NAME        = os.getenv('PROJECT_NAME', 'reyns').lower()
PROJECT_DIR         = os.getenv('PROJECT_DIR', os.getcwd())
DATA_DIR            = os.getenv('DATA_DIR', PROJECT_DIR + '/data_' + PROJECT_NAME)
SERVICES_IMAGES_DIR = os.getenv('SERVICES_IMAGES_DIR', os.getcwd() + '/services')
BASE_IMAGES_DIR     = os.getenv('BASE_IMAGES_DIR', os.getcwd() + '/base')
LOG_LEVEL           = os.getenv('LOG_LEVEL', 'INFO')
SUPPORTED_OSES      = ['ubuntu14.04','centos7.2']
REDIRECT            = '&> /dev/null'

# Sanitize conf
def earlyabort(message):
    print('Aborting due to fatal error at startup: {}.'.format(message))
    sys.exit(1)

if not PROJECT_NAME.strip():
    earlyabort('Got empty "PROJECT_NAME"')
if not PROJECT_DIR.strip():
    earlyabort('Got empty "PROJECT_DIR"')
if not DATA_DIR.strip():
    earlyabort('Got empty "DATA_DIR"')
if not SERVICES_IMAGES_DIR.strip():
    earlyabort('Got empty "SERVICES_IMAGES_DIR"')
if not BASE_IMAGES_DIR.strip():
    earlyabort('Got empty "BASE_IMAGES_DIR"')
if not LOG_LEVEL.strip():
    earlyabort('Got empty "LOG_LEVEL"')
if LOG_LEVEL not in ['DEBUG', 'INFO', 'ERROR', 'CRITICAL']:
    earlyabort('Got unsupported value "{}" for "LOG_LEVEL"'.format(LOG_LEVEL))

# Platform-specific conf tricks
if running_on_windows():
    
    # Don't use redirect as there is no Bash when calling external os_shell calls
    REDIRECT = ''

    # Remove c:/ and similar in data dir and replace with Unix-like /c/
    if len(DATA_DIR) >= 3 and DATA_DIR[1:3] == ':/':
        DATA_DIR = '/{}/{}'.format(DATA_DIR[0].lower(), DATA_DIR[3:])

    # Remove c:/ and similar in project dir and replace with Unix-like /c/
    if len(PROJECT_DIR) >= 3 and PROJECT_DIR[1:3] == ':/':
        PROJECT_DIR_CROSSPLAT = '/{}/{}'.format(PROJECT_DIR[0].lower(), PROJECT_DIR[3:])
else:
    PROJECT_DIR_CROSSPLAT = PROJECT_DIR

# Defaults   
defaults={}
defaults['standard']   = {'linked':True,  'persistent_data':False, 'persistent_opt': False, 'persistent_log':False, 'persistent_home':False, 'publish_ports':False, 'safemode':False, 'interactive':False}
defaults['published']  = {'linked':True,  'persistent_data':False, 'persistent_opt': False, 'persistent_log':False, 'persistent_home':False, 'publish_ports':True,  'safemode':False, 'interactive':False}
defaults['persistent'] = {'linked':True,  'persistent_data':True,  'persistent_opt': False, 'persistent_log':True,  'persistent_home':True,  'publish_ports':False, 'safemode':False, 'interactive':False}
defaults['master']     = {'linked':True,  'persistent_data':True,  'persistent_opt': False, 'persistent_log':True,  'persistent_home':False, 'publish_ports':True,  'safemode':False, 'interactive':False}
defaults['debug']      = {'linked':False, 'persistent_data':False, 'persistent_opt': False, 'persistent_log':False, 'persistent_home':False, 'publish_ports':False, 'safemode':True,  'interactive':True }


#--------------------------
# Logger
#--------------------------

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s: %(message)s')
#logger = logging.getLogger(__name__)
logger = logging.getLogger('Reyns')
logger.setLevel(getattr(logging, LOG_LEVEL))


#--------------------------
# Utility functions & vars
#--------------------------

def safeprint(s):
    try:
        print(s)
    except UnicodeEncodeError:
        if sys.version_info >= (3,):
            print(s.encode('utf8').decode(sys.stdout.encoding))
        else:
            print(s.encode('utf8'))

# Sanitize encoding
def sanitize_encoding(text):
    return text.encode("utf-8", errors="ignore")
    
# Abort
def abort(message):
    print('Aborting due to fatal error: {}. \n'.format(message))
    sys.exit(1)

# Confirm
def confirm(message):
    while True:
        print('{}  [Y/n] '.format(message), end='')
        confirm = raw_input().lower()
        if confirm in ('y', ''):
            return True
        elif confirm == 'n':
            return False
        else:
            print('I didn\'t understand you. Please specify "(y)es" or "(n)o".')

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
    logger.debug('Getting IP address for interface "{}"'.format(ifname))
    if running_on_osx():
        ip_address = os_shell("ifconfig | grep {} -C1 | grep -v inet6 | grep inet | cut -d' ' -f2".format(ifname),capture=True).stdout
        try:
            socket.inet_aton(ip_address)
        except socket.error:
            raise Exception('Error, I could not find a valid IP address for network interface "{}"'.format(ifname))
    else:
        if fcntl:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ip_address = socket.inet_ntoa(fcntl.ioctl(
                s.fileno(),
                0x8915,  # SIOCGIFADDR
                struct.pack('256s', ifname[:15])
            )[20:24])
        else:
            raise Exception('Sorry not supported on this OS (missing fcntl module)') 
    logger.debug('Got IP address for interface "{}": "{}"'.format(ifname,ip_address))
    return ip_address

# More verbose json error message [Removed as does not work anymore in Python 3.6]
#json_original_errmsg = json.decoder.errmsg
#def json_errmsg_plus_verbose(msg, doc, pos, end=None):
#    json.last_error_verbose = doc[pos-15:pos+15].replace('\n','').replace('  ',' ')
#    return json_original_errmsg(msg, doc, pos, end)
#json.decoder.errmsg = json_errmsg_plus_verbose


def sanity_checks(service, instance=None, notrunning_ok=False):
    
    caller = inspect.stack()[1][3]
    clean = True if 'clean' in caller else False
    build = True if 'build' in caller else False
    run   = True if 'run' in caller else False
    ssh   = True if 'ssh' in caller else False
    ip    = True if 'ip' in caller else False
    shell   = True if 'shell' in caller else False
    
    # Shell has same behaviour as ssh for sanity checks
    if shell:
        ssh=True
    
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
                if notrunning_ok:
                    return (None,None)
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
        
        service_dir = get_service_dir(service, onlychecking=True)
        if not os.path.exists(service_dir):
            abort('I cannot find source directory for this service ("{}"). Are you in the project\'s root? I was looking for "{}".'.format(service, service_dir))
  
    # Check instance running if ssh and fixed instance
    if ssh and instance:
        if not get_running_services_instances_matching(service,instance):
            abort('I cannot find any running services for service "{}", instance "{}"'.format(service,instance))
            
    return (service, instance)


def is_base_service(service):
    return (service.startswith('reyns-common-') or service.startswith('reyns-base-') or service.startswith('reyns-dns'))


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

# Check if a customized version of the service exists
def is_customized(service):
    if os.path.isdir('{}/{}_custom'.format(SERVICES_IMAGES_DIR,service)):
        return True
    else:
        return False

# Get service dir for a given service
def get_service_dir(service=None, onlychecking=False):
    if not service:
        raise Exception('get_service_dir: service is required, got "{}"'.format(service))
    
    # Handle the case for base services 
    if is_base_service(service):
        service_dir = BASE_IMAGES_DIR + '/' + service
    else:
        service_dir = SERVICES_IMAGES_DIR + '/' + service

    # Check if customized version for service exists
    if is_customized(service):
        service_dir = service_dir + '_custom'
        if not onlychecking:
            print('Found customized version for this service and using it')

    if not onlychecking:
        logger.debug('Service dir: "{}"'.format(service_dir))

    # Return
    return service_dir

def os_shell(command, capture=False, verbose=False, interactive=False, silent=False):
    '''Execute a command in the os_shell. By default prints everything. If the capture switch is set,
    then it returns a namedtuple with stdout, stderr, and exit code.'''
    
    if capture and verbose:
        raise Exception('You cannot ask at the same time for capture and verbose, sorry')

    # Log command
    logger.debug('Shell executing command: "%s"', command)

    # Execute command in interactive mode    
    if verbose or interactive:
        exit_code = subprocess.call(command, shell=True)
        if exit_code == 0:
            return True
        else:
            return False

    # Execute command getting stdout and stderr
    # http://www.saltycrane.com/blog/2008/09/how-get-stdout-and-stderr-using-python-subprocess-module/
    
    process          = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
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

    conf_file = 'default.conf' if not conf_file else conf_file

    if not conf_file.endswith('.conf'):
        conf_file = conf_file+'.conf'
    
    if os.path.isfile(PROJECT_DIR+'/'+conf_file):
        conf_file_path = PROJECT_DIR+'/'+conf_file
 
    else:
        # If the conf file was explicitly set, then raise, otherwise just return empty conf
        if conf_file != 'default.conf':
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
    valid_service_description_keys = ['service','instance','publish_ports','persistent_data','persistent_opt', 'persistent_log', 'persistent_home',
                                      'links', 'sleep', 'env_vars', 'instance_type', 'volumes', 'nethost', 'safe_persistency','group', 'autorun',
                                      'persistent_shared', 'extra_args', 'publish_ssh_on']
    
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
    
    string  = '\n#---------------------------------'
    string += '\n# Shell exited with exit code {}'.format(exit_code)
    string += '\n#---------------------------------\n'
    string += '\nStandard output: "'
    string += sanitize_encoding(stdout)
    string += '"\n\nStandard error: "'
    string += sanitize_encoding(stderr) +'"\n\n'
    string += '#---------------------------------\n'
    string += '# End Shell output\n'
    string += '#---------------------------------\n'

    return string


def get_service_ip(service, instance):
    ''' Get the IP address of a given service'''
    
    inspect_json = json.loads(os_shell('docker inspect ' + PROJECT_NAME + '-' + service + '-' +instance, capture=True).stdout)
    IP = inspect_json[0]['NetworkSettings']['IPAddress']    

    # The following does not work on WIndows
    # Do not use .format as there are too many graph brackets    
    #IP = os_shell('docker inspect --format \'{{ .NetworkSettings.IPAddress }}\' ' + PROJECT_NAME + '-' + service + '-' +instance, capture=True).stdout

    if IP:
        try:
            socket.inet_aton(IP)
        except socket.error:
            raise Exception('Error, I could not find a valid IP address for service "{}", instance "{}". If the service is running in nethost mode, this is normal'.format(service, instance))
            
    return IP

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


#--------------------------
# Installation management
#--------------------------

#task
def install(how=''):
    '''Install Reyns (user/root)'''
    os_shell(os.getcwd()+'/install.sh {}'.format(how), interactive=True)

#task
def uninstall(how=''):
    '''Uninstall Reyns (user/root)'''
    os_shell(os.getcwd()+'/uninstall.sh {}'.format(how), interactive=True)

#task
def version():
    '''Get Reyns version'''
    
    last_commit_info = os_shell('cd ' + os.getcwd() + ' && git log | head -n3', capture=True).stdout
    if not last_commit_info:
        print('Reyns v0.8.0')
    else:
        print('Reyns v0.8.0')
        last_commit_info_lines = last_commit_info.split('\n')
        commit_shorthash = last_commit_info_lines[0].split(' ')[1][0:7]
        commit_date      = last_commit_info_lines[-1].replace('  ', '')
        print('Current repository commit: {}'.format(commit_shorthash))
        print(commit_date)
    
        python_version = os_shell('python -V', capture=True)
        
        if python_version.stdout:
            print('Python version: {}'.format(python_version.stdout))
        if python_version.stderr:
            print('Python version: {}'.format(python_version.stderr))

#task
def install_demo():
    '''install the Reyns demo in a directory named 'reyns-demo' in the current path'''
    
    INSTALL_DIR = PROJECT_DIR
    
    print('Installing Reyns demo in current directory ({})...'.format(INSTALL_DIR))
    import shutil

    try:
        shutil.copytree(os.getcwd()+'/demo', INSTALL_DIR + '/reyns-demo')
    except OSError as e:
        abort('Could not copy demo data into {}: {}'.format(INSTALL_DIR + '/services', e))
        
    print('\nDemo installed.')
    print('\nQuickstart: enter into "{}/reyns-demo", then:'.format(INSTALL_DIR))
    print('  - to build it, type "reyns build:all";')
    print('  - to run it, type "reyns run:all";')
    print('  - to see running services, type "reyns ps";')
    print('  - to ssh into the "demo", instance "two" service, type "reyns ssh:demo,instance=two";')
    print('    - to ping service "demo", instance "one", type: "ping demo-one";')
    print('    - to exit ssh type "exit";')
    print('  - to stop the demo, type "reyns clean:all".')


#--------------------------
# Services management
#--------------------------

#task
def init(os_to_init='ubuntu14.04', verbose=False, cache=False):
    '''Initialize the base services'''
    
    # Sanity checks:
    if os_to_init not in SUPPORTED_OSES:
        abort('Sorry, unsupported OS. Got "{}" while supported OSes are: {}'.format(os_to_init, SUPPORTED_OSES))
    
    # Switches
    os_to_init  = os_to_init
    verbose     = booleanize(verbose=verbose)
    
    # Build base images
    build(service='reyns-common-{}'.format(os_to_init), verbose=verbose, cache=cache)
    build(service='reyns-base-{}'.format(os_to_init), verbose=verbose, cache=cache)

    if os_to_init=='ubuntu14.04':
        if os_shell('docker inspect reyns/reyns-dns', capture=True).exit_code != 1:
            print('Updating DNS service as well...')
            build(service='reyns-dns-ubuntu14.04', cache=cache)
            out = os_shell('docker tag reyns/reyns-dns-ubuntu14.04 reyns/reyns-dns', capture=True)
            if out.exit_code != 0:
                print(format_shell_error(out.stdout, out.stderr, out.exit_code))
                abort('Something wrong happened, see output above')



#task
def build(service=None, verbose=False, cache=True, relative=True, fromall=False, built=[]):
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
        print('Building all services in {}\n'.format(SERVICES_IMAGES_DIR))

        # Find build hierarchy
        for service in os.listdir(SERVICES_IMAGES_DIR):
            if not os.path.isdir(SERVICES_IMAGES_DIR+'/'+service):
                continue
            if service in built:
                logger.debug('%s already built',service)
                continue
            logger.debug('Processing %s',service)
            try:
                dependencies = find_dependencies(service)
                if dependencies:
                    logger.debug('Service %s depends on: %s',service, dependencies)
                    dependencies.reverse()
                    logger.debug('Dependencies build order: %s', dependencies) 
                    for dependent_service in dependencies:
                        if dependent_service not in built:
                            # Build by recursively calling myself
                            build(service=dependent_service, verbose=verbose, cache=cache, fromall=True, built=built)
                            built.append(dependent_service)
                build(service=service, verbose=verbose, cache=cache, fromall=True)
                built.append(service)
                    
            except IOError:
                pass

    else:
        # Build a given service
        service_dir = get_service_dir(service)

        # Check if we have to exclude this service from autobuild
        if fromall and os.path.isfile(service_dir+'/no_autobuild'):
            logger.debug('Not building service "{}" as "no_autobuild" file present.'.format(service))
            return

        # Build dependencies if not from all
        if not is_base_service(service) and not fromall:
            dependencies = find_dependencies(service)
            if dependencies:
                logger.debug('Service %s depends on: %s',service_dir, dependencies)
                dependencies.reverse()
                logger.debug('Dependencies build order: %s', dependencies)
                print ('This service depends on: {}'.format(dependencies))
                print ('Building dependencies as well to avoid inconsistencies:\n')
                for dependent_service in dependencies:
                    if dependent_service not in built:
                        # Build by recursively calling myself
                        build(service=dependent_service, verbose=verbose, cache=cache, fromall=True, built=built)
                        built.append(dependent_service)
                print ('Done, now building the service:\n')
                        

        # Obtain the base image
        with open('{}/Dockerfile'.format(service_dir)) as f:
            content = f.read()

        image = None
        for line in content.split('\n'):
            if line.startswith('FROM'):
                image = line.strip().split(' ')[-1]

        if not image:
            abort('Missing "FROM" in Dockerfile?!')

        # If reyns's 'FROM' images doe not existe, build them
        if image.startswith('reyns/'):
            logger.debug('Checking image "{}"...'.format(image))
            if os_shell('docker inspect {}'.format(image), capture=True).exit_code != 0:
                print('Could not find Reyns base image "{}", will build it.\n'.format(image))
                build(service=image.split('/')[1], verbose=verbose, cache=cache)

            else:
                logger.debug('Found Reyns base image "{}", will not build it.'.format(image))

        # Default tag prefix to PROJECT_NAME    
        tag_prefix = PROJECT_NAME
        
        # But if we are running a Reyns service, use Reyns image
        if is_base_service(service):
            relative    = False
            tag_prefix  = 'reyns'
            service_dir = 'base/'+service

        # Ok, print the info about the service being built
        print('Building service "{}" as "{}/{}"'.format(service, tag_prefix, service))

        # Check that only a prestartup script is found:
        prestartup_scripts = [f for f in os.listdir(service_dir) if re.match(r'prestartup_+.*\.sh', f)]
        if len(prestartup_scripts) > 1:
            abort("Sorry, found more than one prestartup script for this service an this is not allowed (got {})".format(prestartup_scripts))

        # Update prestartup script date to allow ordered execution
        if prestartup_scripts:
            os_shell('touch {}/{}'.format(service_dir, prestartup_scripts[0]),silent=True)
 
        # Automatically set buildinguser/group args. This is experimental and only for Linux, since
        # Mac remaps everything on the user running Docker and Windows has no uid/gid support in Python.
        # Moreover, this is useless with safe persistency on. TODO: Do we want to keep this?
        set_user_uid_gid_args = ''
        if running_on_unix():
            import pwd, grp
            user_group_info = {}
            user_group_info['BUILDING_UID'] = os.getuid()
            user_group_info['BUILDING_GID'] = pwd.getpwuid(user_group_info['BUILDING_UID']).pw_gid
            user_group_info['BUILDING_USER'] = pwd.getpwuid(user_group_info['BUILDING_UID']).pw_name
            user_group_info['BUILDING_GROUP'] = grp.getgrgid(user_group_info['BUILDING_GID']).gr_name

            # Obtain the arguments from the Dockerfile
            try:
                with open(service_dir+'/Dockerfile') as f:
                    dockerfile = f.readlines()
            except IOError:
                abort('No Dockerfile found (?!) I was looking in {}'.format(service_dir+'/Dockerfile'))
    
            for i,line in enumerate(dockerfile):
                if line.startswith('ARG'):
                    try:
                        build_arg =  line.replace('\n','').strip().split(' ')[1]
                    except IndexError:
                        abort('Error in parsing building args, Dockerfile line #{} ("{}")'.format(i,line.strip()))
                    try:
                        set_user_uid_gid_args += '--build-arg {}={} '.format(build_arg, user_group_info[build_arg])
                    except KeyError:
                        pass

            # Strip trailing space
            set_user_uid_gid_args = set_user_uid_gid_args.strip()

        # Build command
        if relative:
            if not cache:
                print('Building without cache')
                build_command = 'cd ' + service_dir + '/.. &&' + ' docker build ' + set_user_uid_gid_args + ' --no-cache -t ' + tag_prefix +'/' + service + ' ' + service_dir
            else:
                print('Building with cache')
                build_command = 'cd ' + service_dir + '/.. &&' + ' docker build ' + set_user_uid_gid_args + ' -t ' + tag_prefix +'/' + service + ' ' + service_dir
        else:
            if not cache:
                print('Building without cache')
                build_command = 'docker build  ' + set_user_uid_gid_args + ' --no-cache -f '+ service_dir + '/Dockerfile -t ' + tag_prefix +'/' + service + ' .'
            else:
                print('Building with cache')
                build_command = 'docker build ' + set_user_uid_gid_args + ' -f '+ service_dir + '/Dockerfile -t ' + tag_prefix +'/' + service + ' .'
                
                           
        logger.debug('Build command: "{}"'.format(build_command))    
        
        # Build
        print('Building...')
        if verbose:
            if os_shell(build_command, verbose=True):
                print('Build OK\n')
            else:
                print('')
                abort('Something wrong happened, see output above. Reminder: in case of remote repositories errors (i.e. 404 Not Found) try to build without cache to refresh remote repositories lists (i.e. build:all,cache=False)')
        else:
            if os_shell(build_command, verbose=False, capture=False, silent=True):
                print('Build OK\n')
            else:
                abort('Something wrong happened, see output above. Reminder: in case of remote repositories errors (i.e. 404 Not Found) try to build without cache to refresh remote repositories lists (i.e. build:all,cache=False)')




#task
def start(service,instance=None):
    '''Start a stopped service. Use only if you know what you are doing.'''
    
    # Default tag prefix to PROJECT_NAME    
    tag_prefix = PROJECT_NAME

    # But if we are running a Reyns service, use Reyns image
    if is_base_service(service):
        tag_prefix = 'reyns'
    
    if service_exits_but_not_running(service,instance):
        os_shell('docker start {}-{}-{}'.format(tag_prefix,service,instance), silent=True)
    else:
        abort('Cannot start a service not in exited state. use "run" instead')

#task
def stop(service,instance=None):
    '''Stop a stopped service. Use only if you know what you are doing.'''
    running_instances = get_running_services_instances_matching(service,instance)
    if len(running_instances) == 0:
        if instance:
            abort('Could not find any instance named "{}" for service "{}"'.format(instance, service))   
        else:
            abort('Could not find any running instance of service matching "{}"'.format(service))                
    if len(running_instances) > 1:
        abort('Found more than one running instance for service "{}": {}, please specity wich one.'.format(service, running_instances))            
    service = running_instances[0][0]
    instance  = running_instances[0][1]

    # Default tag prefix to PROJECT_NAME    
    tag_prefix = PROJECT_NAME

    # But if we are running a Reyns service, use Reyns image
    if is_base_service(service):
        tag_prefix = 'reyns'
    
    if is_service_running(service,instance):
        os_shell('docker stop {}-{}-{}'.format(tag_prefix,service,instance), silent=True)
    else:
        abort('Service is not in runnign state, cannot stop.')


#task
def rerun(service, instance=None):
    '''Re-run a given service (instance is not mandatory if only one is running)'''
    running_instances = get_running_services_instances_matching(service,instance)
    if len(running_instances) == 0:
        if instance:
            abort('Could not find any instance named "{}" for service "{}"'.format(instance, service))   
        else:
            abort('Could not find any running instance of service matching "{}"'.format(service))                
    if len(running_instances) > 1:
        abort('Found more than one running instance for service "{}": {}, please specity wich one.'.format(service, running_instances))            
    service = running_instances[0][0]
    instance  = running_instances[0][1]

    # Clean    
    clean(service,instance)
    run(service,instance,from_rerun=True)


# TODO: clarify difference between False and None.
#task
def run(service=None, instance=None, group=None, instance_type=None, interactive=None, 
        persistent_data=None, persistent_opt=None, persistent_log=None, persistent_home=None,
        publish_ports=None, linked=None, seed_command=None, conf=None, safemode=None,
        recursive=False, from_rerun=False, nethost=None, extra_args=None, publish_ssh_on=None):
    '''Run a given service with a given instance. If no instance name is set,
    a standard instance with a random name is run. If service name is set to "all"
    then all the services are run, according to the conf.'''

    #------------------------
    # Handle conf(s)
    #------------------------

    # Load host conf 
    host_conf = load_host_conf()
    
    # Handle last run conf
    try:
        last_conf = host_conf['last_conf']
        #if not conf:
        #    conf = last_conf
    except KeyError:
        if conf:
            host_conf['last_conf'] = conf
            save_host_conf(host_conf)
    else:
        if last_conf != conf:
            host_conf['last_conf'] = conf
            save_host_conf(host_conf)

    if not recursive:
        print('Conf being used: "{}"'.format('default' if not conf else conf))
    
    #---------------------------
    # Run a group of services
    #---------------------------
    if service == 'all' or group:
        
        if service == 'all':
            #print('WARNING: using the magic keyword "all" is probably going to be deprecated, use group=all instead.')
            group = 'all'
        
        print('\nRunning services in {} for group {}'.format(SERVICES_IMAGES_DIR,group))

        if safemode or interactive:
            abort('Sorry, you cannot set one of the "safemode" or "interactive" switches if you are running more than one service') 

        # Load run conf             
        try:
            services_to_run_confs = get_services_run_conf(conf)
        except Exception as e:
            abort('Got error in reading run conf for automated execution: {}.'.format(e))

        if not services_to_run_confs:
            
            # TODO: Move this in a separate routine (duplicate from beginning of get_services_run_conf)
            conf_file = 'default.conf' if not conf else conf
            if not conf_file.endswith('.conf'):
                conf_file = conf_file + '.conf'
            
            abort('No or empty conf file (looking for "{}"), are you in the project\'s root?'.format(conf_file))
        
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
            else:
                if 'autorun' in service_conf:
                    if not service_conf['autorun']:
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
                persistent_home = persistent_home if persistent_home is not None else (service_conf['persistent_home'] if 'persistent_home' in service_conf else None),
                publish_ports   = publish_ports   if publish_ports   is not None else (service_conf['publish_ports']   if 'publish_ports'   in service_conf else None),
                linked          = linked          if linked          is not None else (service_conf['linked']          if 'linked'          in service_conf else None),
                interactive     = interactive,
                safemode        = safemode,
                conf            = conf,
                extra_args      = extra_args,
                recursive       = True)
                
        # Exit
        return

    #-----------------------
    # Run a given service
    #-----------------------
    
    # Sanitize...
    (service, instance) = sanity_checks(service, instance)

    # Layout
    print('')

    # Set service dir
    service_dir = get_service_dir(service)

    # Chek if we have to build a Reyns a missing service, and specifically the DNS
    if service == 'reyns-dns' :
        if os_shell('docker inspect reyns/reyns-dns', capture=True).exit_code != 0:
            print('\nMissing DNS service, now building it...')
            build(service='reyns-dns-ubuntu14.04')
            out = os_shell('docker tag reyns/reyns-dns-ubuntu14.04 reyns/reyns-dns', capture=True)
            if out.exit_code != 0:
                print(format_shell_error(out.stdout, out.stderr, out.exit_code))
                abort('Something wrong happened, see output above')



    # Run a specific service
    print('Running service "{}" ("{}/{}"), instance "{}"...'.format(service, PROJECT_NAME, service, instance))

    # Check if this service is exited
    if service_exits_but_not_running(service,instance):

        abort('Service "{0}", instance "{1}" exists but it is not running, I cannot start it since the linking ' \
              'would be end up broken. Use reyns clean:{0},instance={1} to clean it and start over clean, ' \
              'or reyns _start:{0},instance={1} if you know what you are doing.'.format(service,instance))

    # Check if this service is already running
    if is_service_running(service,instance):
        print('Service is already running, not starting.')
        # Exit
        return    

    # Init service conf, requested env vars and privileged switch
    service_conf = None
    ENV_VARs     = {}
    privileged   = False

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
            conf_file = conf if conf else 'default'
            if not confirm('WARNING: Could not find conf for service {}, instance {} in the conf in use ("{}"). Should I proceed?'.format(service, instance, conf_file)):
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
 
    # Prelminary set of switches
    persistent_data = persistent_data if persistent_data is not None else (service_conf['persistent_data'] if 'persistent_data' in service_conf else None)
    persistent_log  = persistent_log  if persistent_log  is not None else (service_conf['persistent_log']  if 'persistent_log'  in service_conf else None)
    persistent_opt  = persistent_opt  if persistent_opt  is not None else (service_conf['persistent_opt']  if 'persistent_opt'  in service_conf else None)
    persistent_home = persistent_home if persistent_home is not None else (service_conf['persistent_home'] if 'persistent_home'  in service_conf else None)
    publish_ports   = publish_ports   if publish_ports   is not None else (service_conf['publish_ports']   if 'publish_ports'   in service_conf else None)
    linked          = linked          if linked          is not None else (service_conf['linked']          if 'linked'          in service_conf else None)               
    nethost         = nethost         if nethost         is not None else (service_conf['nethost']         if 'nethost'         in service_conf else None)

    # Handle the instance type.
    if not instance_type:
        if 'instance_type' in service_conf:
                instance_type = service_conf['instance_type']
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
    persistent_home = setswitch(persistent_home=persistent_home, instance_type=instance_type)    
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
    ENV_VARs['PERSISTENT_HOME'] = persistent_home
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
                    if link_instance:
                        logger.info('Could not find a running instance named "{}" of service "{}" which is required for linking by service "{}", instance "{}". I will expect an env var for proper linking setup'.format(link_instance, link_service, service, instance))
                    else:
                        logger.info('Could not find any running instance of service matching "{}" which is required for linking by service "{}", instance "{}". I will expect an env var for proper linking setup'.format(link_service, service, instance))
                    ENV_VARs[link_name.upper()+'_SERVICE_IP'] = None
                    
                else:
                    if len(running_instances) > 1:
                        logger.warning('Found more than one running instance for service "{}" which is required for linking: {}. I will use the first one ({}). You can set explicity on which instance to link on in the conf file'.format(link_service, running_instances, running_instances[0]))
                      
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
        elif service == 'reyns-dns':
            abort('SERVICE_IP env var is required when publishing the reyns-dns service')            
        else:
            pass
            # TODO: improve the followign warning, decide if show it or not and in which conditions (i.e. MULTIHOST env var?)
            #logger.warning('You are publishing the service but you have not set the SERVICE_IP env var. This mean that the service(s) might not be completely accessible outside the Docker network.')

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


    # Handle safe persistency
    if service_conf and 'safe_persistency' in service_conf and service_conf['safe_persistency']:
        ENV_VARs['SAFE_PERSISTENCY'] = True
        privileged = True

    # Handle persistency
    if persistent_data or persistent_log or persistent_opt or persistent_home:

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
        if service_conf and 'safe_persistency' in service_conf:
            run_cmd += ' -v {}:/safe_persistent'.format(service_instance_dir)
        else:
            run_cmd += ' -v {}:/persistent'.format(service_instance_dir)

    # Handle shared data between all instances
    if service_conf and 'persistent_shared' in service_conf and service_conf['persistent_shared']:
        if not os.path.exists(DATA_DIR+'/shared'):
            os.makedirs(DATA_DIR+'/shared')
        run_cmd += ' -v {}/shared:/shared'.format(DATA_DIR)
    else:
        # The following is a Doker Volume, not to be confused with a path
        run_cmd += ' -v {}-shared:/shared'.format(PROJECT_NAME)

    # Clean temp volume for this service/instance if any was lefted over from previous half-successful runs...
    os_shell('docker volume rm {}-{}-{}-tmp {}'.format(PROJECT_NAME, service,instance, REDIRECT), capture=True)

    # TODO: reading service conf like above is wrong, conf should be loaded at beginning and now we should have only variables.
    # Handle extra volumes
    if service_conf and 'volumes' in service_conf:
        volumes = service_conf['volumes'].split(',')
        for volume in volumes:
            if volume.startswith('$PROJECT_DIR'):
                # Project dir wildard. This is beacuse Docker does not allow relitive paths, basically.
                volume = volume.replace('$PROJECT_DIR', PROJECT_DIR_CROSSPLAT)
                run_cmd += ' -v {}'.format(volume)
            elif volume.startswith('$TEMP_VOLUME'):
                # Temp volume
                if volume.split(':')[0] in ['$TEMP_VOLUME', '$TEMP_VOLUME/']:
                    run_cmd += ' -v {}-{}-{}-tmp:{}'.format(PROJECT_NAME,service,instance,volume.split(':')[1])
                else:
                    abort('You cannot use any path in the temp volume')
            else:
                # Standard (folder) volume
                run_cmd += ' -v {}'.format(volume)
    
    # Handle extra (Docker) args
    if not extra_args and service_conf and 'extra_args' in service_conf:
        extra_args = service_conf['extra_args']
    if extra_args:
        run_cmd += ' {}'.format(extra_args)

    # Handle publish ssh port
    if not publish_ssh_on and service_conf and 'publish_ssh_on' in service_conf:
        publish_ssh_on = service_conf['publish_ssh_on']
    if publish_ssh_on:
        run_cmd += ' -p{}:22'.format(publish_ssh_on)

    # Init ports lists
    ports =     []
    udp_ports = []
    
    # If is dns service:
    if service == 'reyns-dns' :
        ports.append('53')
        udp_ports.append('53')
        
    # Handle Reyn's annotations
    if not is_base_service(service):
        try:
            with open(service_dir+'/Dockerfile') as f:
                dockerfile = f.readlines()
        except IOError:
            abort('No Dockerfile found (?!) I was looking in {}'.format(get_service_dir(service)+'/Dockerfile'))
        
    
        for line in dockerfile:
            
            # Clean up text
            line = line.strip()
            
            # Check if comment line
            if line.startswith('#'):
    
                # Re-clean text
                comment = line[1:].strip()
    
                # Look for a Reyns' annotation
                if comment.startswith('reyns:'):
    
                    # Re-re clean text
                    reyns_annotation = comment[6:].strip()
    
                    # Init avalid annotation commands
                    annotation_commands= ['expose', 'privileged']
                    found_valid_annotation_command = False
                    
                    # Look if we have a valid annotation command
                    for annotation_command in annotation_commands:
    
                        if reyns_annotation.startswith(annotation_command):
    
                            # Set annotation command and annotation command arg
                            annotation_command_arg = reyns_annotation.replace(annotation_command,'').strip()
    
                            # Handle the annotation command. This part will need to be refacotered/decoupled
    
                            #--------------------------------
                            # Expose annotation command
                            #--------------------------------
                            if annotation_command == 'expose':
                                
                                # Handle exposing (publishing) ports as other ports 
                                if 'as' in annotation_command_arg:
                                    # Obtain container and host ports
                                    try:
                                        (container_port, host_port) = annotation_command_arg.split('as')
                                    except ValueError:
                                        abort('Too many sub-arguments in annotation command argument "{}"'.format(annotation_command_arg))
                                    container_port = container_port.strip()
                                    host_port      = host_port.strip() 
                                else:
                                    container_port = host_port = annotation_command_arg
        
    
                                # Do we have a specific protocol in source or dest port?
                                if '/' in container_port:
                                    try:
                                        container_port_number, container_port_protocol = container_port.split('/')
                                    except ValueError:
                                        abort('Too many slashes in port definiton ("{}")'.format(container_port))
                                else:
                                    container_port_number  = container_port
                                    container_port_protocol = 'tcp'
                                
                                if '/' in host_port:
                                    try:
                                        host_port_number, host_port_protocol = host_port.split('/')
                                    except ValueError:
                                        abort('Too many slashes in port definiton ("{}")'.format(host_port))
                                else:
                                    host_port_number   = host_port
                                    host_port_protocol = 'tcp'
    
                                # Check taht we have valid port numbers
                                try:
                                    container_port_number = int(container_port_number)
                                except ValueError:
                                    abort('Port value "{}" is not valid'.format(container_port_number))
                                try:
                                    host_port_number = int(host_port_number)
                                except ValueError:
                                    abort('Port value "{}" is not valid'.format(host_port_number))
            
                                # Check we have a valid protocolol and that it is the same between source and dest ports
                                if container_port_protocol not in ['tcp', 'udp']:
                                    abort('Unknown expose protocol "{}"'.format(container_port_protocol))
                                if host_port_protocol not in ['tcp', 'udp']:
                                    abort('Unknown expose protocol "{}"'.format(host_port_protocol))
                                if container_port_protocol != host_port_protocol:
                                    abort('Expose container port protocol "{}" and host port protocol "{}" are not the same.'.format(container_port_protocol,host_port_protocol))
                                else:
                                    ports_protocol = container_port_protocol
    
                                # Ok, add this port mapping to the container (if we have to publish it)
                                if publish_ports:
                                    if ports_protocol == 'tcp':
                                        ports.append([container_port_number,host_port_number])
                                    elif ports_protocol == 'udp':
                                        udp_ports.append([container_port_number,host_port_number])
    
    
                            #--------------------------------
                            # Privileged annotation command
                            #--------------------------------
                            elif annotation_command == 'privileged':
                                privileged=True
    
    
                            #--------------------------------
                            # Inconsistent annotation command
                            #--------------------------------                       
                            else:                            
                                abort('Inconsistent annotation command "{}"'.format(annotation_command))
                        
                            # We validated this command, noo net to go trought the others
                            found_valid_annotation_command = True
                            # Also we can stop here, no need to go trought the rest
                            break
    
                    # If no valid annotation command found abort
                    if not found_valid_annotation_command:
                        abort('Got Reyns annotation with unknown command (annotation="{}")'.format(reyns_annotation))
                   

    # Handle privileged mode
    if privileged:
        run_cmd += ' --privileged'
               
    # Handle published ports
    if publish_ports:

        # Handle forcing of an IP where to publish the ports
        if 'PUBLISH_ON_IP' in ENV_VARs:
            pubish_on_ip = ENV_VARs['PUBLISH_ON_IP']+':'
        elif 'SERVICE_IP' in ENV_VARs:
            pubish_on_ip = ENV_VARs['SERVICE_IP']+':'
        else:
            pubish_on_ip = ''

        # TCP ports publishing
        for port in ports:
            if isinstance(port, list):
                container_port = port[0]
                host_port = port[1]
            else: 
                container_port = port
                host_port = port
            run_cmd += ' -p {}{}:{}'.format(pubish_on_ip, host_port, container_port)

        # UDP ports publishing
        for port in udp_ports:
            if isinstance(port, list):
                container_port = port[0]
                host_port = port[1]
            else: 
                container_port = port
                host_port = port
            run_cmd += ' -p {}{}:{}/udp'.format(pubish_on_ip, container_port, host_port)

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

    # But if we are running a Reyns service, use Reyns image
    if is_base_service(service):
        tag_prefix = 'reyns'

    if interactive:
        run_cmd += ' --rm  -i -t {}/{}:latest {}'.format(tag_prefix, service, seed_command)
        os_shell(run_cmd,interactive=True)
        
    else:
        run_cmd += ' -d -t {}/{}:latest {}'.format(tag_prefix, service, seed_command)   
        
        out = os_shell(run_cmd, capture=True)
        if out.exit_code:
            print(format_shell_error(out.stdout, out.stderr, out.exit_code))
            abort('Something failed when executing "docker run"')
        
        container_id = out.stdout
        
        # Chech logs and wait untill prestartup scripts are executed (both correctly and incorrectly)
        # TODO: this check is weak, improve it!
        ok_string    = '[INFO] Executing Docker entrypoint command'
        error_string = '[ERROR] Exit code'
        
        print('Waiting for pre-startup scripts to be executed...')
        while True:
            
            # Check for ok or error strings in container output
            check_cmd = 'docker logs {}'.format(container_id)
            out = os_shell(check_cmd, capture=True)
            
            # Docker logs command merge container stdout and stderr into stdout
            out_lines = out.stdout.split('\n')
            
            # Check if we have ok or error string in output lines
            passed = None
            for line in out_lines:
                if ok_string in line:
                    passed = True             
                if error_string in line:
                    passed = False

            # Handle passed / not passed / unknown
            if passed == True:
                break
            elif passed == False:
                for line in out_lines:
                    print(line)
                abort('Error in service prestartup phase. Check output above') 
            else:
                sleep(1)
            
        print('Done.')
   
    # In the end, the sleep..
    if service_conf and 'sleep' in service_conf:
        if not interactive and not from_rerun:
            to_sleep = int(service_conf['sleep'])
            if to_sleep:
                print('Now sleeping {} seconds to allow service setup...'.format(to_sleep))
                sleep(to_sleep)
 
    
    
#task
def clean(service=None, instance=None, group=None, force=False, conf=None):
    '''Clean a given service. If service name is set to "all" then clean all the services according 
    to the conf. If service name is set to "reallyall" then all services on the host are cleaned'''

    # all: list services to clean (check run conf first)
    # reallyall: warn and clean all
    
    if service == 'reallyall':        
        if confirm('Clean all services? WARNING: this will stop and remove *really all* Docker services running on this host!'):
            print('Cleaning all Docker services on the host...')
            os_shell('docker stop $(docker ps -a -q) ' + REDIRECT, silent=True)
            os_shell('docker rm $(docker ps -a -q) ' + REDIRECT, silent=True)

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
                
        print('Conf being used: "{}"'.format('default' if not conf else conf))

        if service == 'all':
            #print('WARNING: using the magic keyword "all" is probably going to be deprecated, use group=all instead.')
            group = 'all'        

        # Get service list to clean
        one_in_conf = False
        services_run_conf = []
        for service_conf in get_services_run_conf(conf):
            
            # Do not clean instances not explicity set in conf file (TODO: do we want this?)
            if not service_conf['instance']:
                continue
            
            # Do not clean instances not belonging to the group we want to clean
            if group != 'all' and 'group' in service_conf and service_conf['group'] != group:
                continue
            
            # Understand if the service to clean is running
            if is_service_running(service=service_conf['service'], instance=service_conf['instance']) \
              or service_exits_but_not_running(service=service_conf['service'], instance=service_conf['instance']):
                if not one_in_conf:
                    print('\nThis action will clean the following services instances according to the conf:')
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
            if not force:
                print ('')
            for service_conf in services_to_clean_conf:
                if not service_conf['instance']:
                    print('WARNING: I Cannot clean {}, instance='.format(service_conf['service'], service_conf['instance']))
                else:
                    print('Cleaning service "{}", instance "{}"..'.format(service_conf['service'], service_conf['instance']))          
                    os_shell("docker stop "+PROJECT_NAME+"-"+service_conf['service']+"-"+service_conf['instance']+" " + REDIRECT, silent=True)
                    os_shell("docker rm "+PROJECT_NAME+"-"+service_conf['service']+"-"+service_conf['instance']+" " + REDIRECT, silent=True)
                            
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
                
        print('Conf being used: "{}"'.format('default' if not conf else conf))

        # Sanitize (and dynamically obtain instance)...
        (service, instance) = sanity_checks(service,instance, notrunning_ok=force)
        
        if not instance:
            print('I did not find any running instance to clean, exiting. Please note that if the instance is not running, you have to specify the instance name to let it be clened')
        else:
            print('Cleaning service "{}", instance "{}"..'.format(service,instance))   
            os_shell("docker stop "+PROJECT_NAME+"-"+service+"-"+instance+" " + REDIRECT, silent=True)
            os_shell("docker rm "+PROJECT_NAME+"-"+service+"-"+instance+" " + REDIRECT, silent=True)

    # Also, remove shared volume (and ignore any error which means it is still in use):
    os_shell('docker volume rm {}-shared {}'.format(PROJECT_NAME, REDIRECT), capture=True)
    # ..and temp volume, ignoring errors which mean it does not exist (never requested)
    os_shell('docker volume rm {}-{}-{}-tmp {}'.format(PROJECT_NAME, service,instance, REDIRECT), capture=True)


#task
def ssh(service=None, instance=None, command=None, capture=False, jsonout=False):
    '''SSH into a given service'''
    
    # Sanitize input
    if capture and jsonout:
        abort('Sorry, you enabled both capture and jsonout but you can only use one at a time.')
    
    # Sanitize...
    (service, instance) = sanity_checks(service,instance)
    
    if not running_on_osx():
        try:
            IP = get_service_ip(service, instance)
        except Exception as e:
            abort('Got error when obtaining IP address for service "{}", instance "{}": "{}"'.format(service,instance, e))
        if not IP:
            abort('Got no IP address for service "{}", instance "{}"'.format(service,instance))

    # Check if the key has proper permissions
    if not os_shell('ls -l keys/id_rsa',capture=True).stdout.endswith('------'):
        os_shell('chmod 600 keys/id_rsa', silent=True)

    # Set default port
    port = 22

    # Workaround for bug in OSX
    # See https://github.com/docker/docker/issues/22753
    if running_on_osx():

        # Get container ID
        console_out = os_shell('reyns info:{},{}'.format(service,instance),capture=True)
        #DEBUG print(console_out)            
        info = console_out.stdout.split('\n')
        container_id = info[2].strip().split(' ')[0]

        # Get inspect data
        console_out = os_shell('docker inspect {}'.format(container_id),capture=True)
        #DEBUG print(console_out)
        inspect = json.loads(console_out.stdout)

        # Check that we are operating on the right container
        if not inspect[0]['Id'].startswith(container_id):
            abort('Reyns internal error (containers ID do not match)')

        # Get host's port for SSH forwarding
        try:
            port = inspect[0]['NetworkSettings']['Ports']['22/tcp'][0]['HostPort']
        except KeyError:
            try:
                port = inspect[0][u'HostConfig']['PortBindings']['22/tcp'][0]['HostPort']
            except KeyError as e:
                abort('Cannot find ssh port, is the service correctly configured? (KeyError: {})'.format(e))

        # Set IP to localhost
        IP = '127.0.0.1'

    # RUN command over SSH or SSH session
    if command:
        if capture:
            out = os_shell(command='ssh -t -p {} -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -i keys/id_rsa reyns@{} -- "{}"'.format(port, IP, command), capture=True)
            return out
        elif jsonout:
            out = os_shell(command='ssh -t -p {} -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -i keys/id_rsa reyns@{} -- "{}"'.format(port, IP, command), capture=True)
            out_dict = {'stdout': out.stdout, 'stderr':out.stderr, 'exit_code':out.exit_code}
            print(json.dumps(out_dict)) # This goes to stdout and is ready to be loaded as json             
        else:
            os_shell(command='ssh -t -p {} -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -i keys/id_rsa reyns@{} -- "{}"'.format(port, IP, command), interactive=True)
            
    else:
        os_shell(command='ssh -t -p {} -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -i keys/id_rsa reyns@{}'.format(port, IP), interactive=True)

#task
def shell(service=None, instance=None, command=None, capture=False, jsonout=False):
    '''Open a shell into a given service (via Docker exec)'''
    
    # Sanitize input
    if capture and jsonout:
        abort('Sorry, you enabled both capture and jsonout but you can only use one at a time.')
    
    # Sanitize...
    (service, instance) = sanity_checks(service,instance)

    container_id = os_shell('docker ps -a | grep "{}-{}"'.format(service,instance), capture=True).stdout.split(' ')[0]

    # RUN command over SSH or SSH session
    if command:
        if capture:
            out = os_shell(command='docker exec -it {} sudo -i -u reyns bash -c "{}"'.format(container_id, command), capture=True)
            return out
        elif jsonout:
            out = os_shell(command='docker exec -it {} sudo -i -u reyns bash -c "{}"'.format(container_id, command), capture=True)
            out_dict = {'stdout': out.stdout, 'stderr':out.stderr, 'exit_code':out.exit_code}
            print(json.dumps(out_dict)) # This goes to stdout and is ready to be loaded as json             
        else:
            os_shell(command='docker exec -it {} sudo -i -u reyns bash -c "{}"'.format(container_id, command), interactive=True)
            
    else:
        os_shell(command='docker exec -it {} sudo -i -u reyns bash '.format(container_id), interactive=True)

#task
# Deprecated, included in the tasks handling in the main
#def help():
#    '''Show this help'''
#    os_shell('fab --list', capture=False)

#task
def getip(service=None, instance=None):
    '''Get a service IP'''

    # Sanitize...
    (service, instance) = sanity_checks(service,instance)
    
    # Get running instances
    running_instances = get_running_services_instances_matching(service)
    # For each instance found print the ip address
    for i in running_instances:
        print('IP address for {} {}: {}'.format(i[0], i[1], get_service_ip(i[0], i[1])))

# TODO: split in function plus task, allstates goes in the function

#task
def info(service=None, instance=None, capture=False):
    '''Obtain info about a given service'''
    return ps(service=service, instance=instance, capture=capture, info=True)

#task
def ps(service=None, instance=None, capture=False, onlyrunning=False, info=False, conf=None):
    '''Info on running services. Give a service name to obtain informations only about that specific service.
    Use the magic words 'all' to list also the not running ones, and 'reallyall' to list also the services not managed by
    Reyns (both running and not running)'''

    # TODO: this function has to be COMPLETELY refactored. Please do not look at this code.
    # TODO: return a list of namedtuples instead of a list of lists

    known_services_fullnames          = None

    if not service:
        service = 'project'

    if not info and service not in ['all', 'platform', 'project', 'reallyall']:
        abort('Sorry, I do not understand the argument "{}"'.format(service))

    # TODO: The following is a leftover from project/platform division and prbably does nto even work
    if service == 'platform':
        known_services_fullnames = [conf['service']+'-'+conf['instancef'] for conf in get_services_run_conf(conf)]
        
    # Handle magic words all and reallyall
    if onlyrunning: # in ['all', 'reallyall']:
        out = os_shell('docker ps', capture=True)
        
    else:
        out = os_shell('docker ps -a', capture=True)
    
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
 
                    # Handle Reyns services service
                    if ('-' in service_name) and (not service == 'reallyall') and (service_name.startswith(PROJECT_NAME+'-')):
                        if known_services_fullnames is not None:
                            # Filter against known_services_fullnames
                            if service_name not in known_services_fullnames:
                                logger.info('Skipping service "{}" as it is not recognized by Reyns. Use the "all" magic word to list them'.format(service_name))
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
                            
                    # Handle non-Reyns services 
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

def status():
    running_services = ps(capture=True)
    one_running = False
    for running_service in running_services:
        one_running = True
        
        # GEt basic service info
        fullname = running_service[-1]
        service  = running_service[-1].split(',')[0]
        instance = running_service[-1].split('=')[1]
        status   = running_service[4]
        id       = running_service[0]
        
        print ('{} : {}'.format(fullname, status ))
        
        # Get supervisorctl status info
        if status.lower().startswith('up'):
            #out = ssh(service,instance,command="sudo supervisorctl status",capture=True)
            out = os_shell('docker exec -it {} supervisorctl status'.format(id), capture=True)
            if out.exit_code != 0:
                if out.stderr: print(out.stderr)
                if out.stdout: print(out.stdout)
            else:
                for line in out.stdout.split('\n'):
                    print('  {}'.format(line))
                print('')
        
    if not one_running:
        print('No running services.')







#--------------------
#   M A I N
#--------------------

class InputException(Exception):
    pass

def make_it_a_duck(val):
    # True
    if val.lower() == 'true':
        val = True
        return val
    
    # False
    if val.lower() == 'false':
        val = False
        return val
    
    # Int
    try:
        val =int(val)
        return val
    except:
        pass

    # Float
    try:
        val = float(val)
        return val
    except:
        pass
    
    # Original
    return val




if __name__ == '__main__':
    
    # Get task and args 
    if len(sys.argv) == 1:
        help()
        
    elif len(sys.argv) == 2:
        # This happens on some OSes
        args = sys.argv[1]
        
    else:
        # This happens on some other OSes
        args = ' '.join(sys.argv[1:])

    # Get task from args
    if ':' in args:
        task=None
        try:
            args_pieces  = args.split(':')
            task = args_pieces[0]
            args = ':'.join(args_pieces[1:])
        except (ValueError, IndexError):
            raise InputException('Erro in parsing command arguments: task={} args="{}"'.format(task,args))
    else:
        task = sys.argv[1]
        args = None

    # Debug
    logger.debug('Task: %s' % task)
    logger.debug('Args: %s' % args)
        
    # Examples:
    # reyns ssh:demo,one,command="whoami \&>/dev/null",verbose=True
    # reyns ssh:demo,one,command="echo \$PATH && ps -ef"
    # reyns ssh:demo,one,command=echo \$PATH \&\& ps -ef
    # reyns ssh:demo,one,command="whoami \& >/dev/null"
    # reyns ssh:demo,one,command="cat /etc/resolv.conf"
    # reyns ssh:demo,one,command="cat \/etc\/resolv.conf"
        
    # Note: the Bash script which inovokes this Python script ensures that
    # there will never be an empty task, as not having arguments on command line 
    # lead to defaulting to the "help" task. TODO: this is not robust, improve it. 

    argv   = []
    kwargs = {}

    # Comma is the only forbidden char in SSH commands (for now)
    if args:
        if ',' in args:
            parts = args.split(',')
        else:
            parts = [args] 
        
        # Create argv and kwargs 
        for i, part in enumerate(parts):
            if '=' in part:
                arg = part.split('=')[0]
                val = '='.join(part.split('=')[1:])
                kwargs[arg] = make_it_a_duck(val)
            else:
                if kwargs:
                    raise InputException('non-kwarg after kwarg')
                arg = i
                val = part
                argv.append(make_it_a_duck(val))
    
    # Debug
    logger.debug('Processed argv: %s' % argv)
    logger.debug('Processed kwargs: %s' % kwargs)

    # Tasks mapping
    from collections import OrderedDict
    tasks = OrderedDict()
    tasks['build']        = [build, '    Build services' ]
    tasks['run']          = [run, '      Run a given service(s)'] 
    tasks['rerun']        = [rerun, '    Re-run a given service(s)'] 
    tasks['ps']           = [ps, '       List running services' ]    
    tasks['status']       = [status, '   Running services status' ] 
    tasks['ssh']          = [ssh, '      SSH into a given service']
    tasks['shell']        = [shell, '    Open a shell into a given service']
    tasks['clean']        = [clean, '    Clean a given service']
    tasks['getip']        = [getip, '    Get the IP address of a given service']
    tasks['info']         = [info, '     Obtain info about a given service']    
    tasks['install_demo'] = [install_demo, '     Install demo project in current directory']  
    tasks['help']         = [help, '     Show this help']  
    tasks['version']      = [version, '  Get Reyns version']
    tasks['uninstall']    = [uninstall, 'Uninstall Reyns' ]
    tasks['init']         = [init, '    Init base Reyns images' ]
    tasks['_install']     = [install, ' Install Reyns' ]
    tasks['_start']       = [start, '   Start a stopped service (if you know what you are doing)' ]
    tasks['_stop']        = [stop, '    Stop a running service (if you know what you are doing)' ]

    # Output cleareness
    if ('jsonout' not in kwargs) or ('jsonout' in kwargs and kwargs['jsonout']==False):
        print('')
        
    # Load proper task
    if (task == 'help') or (not task and not argv and not kwargs):
        print('Available commands:\n')
        for task in tasks:
            if task[0] != '_':
                print('  {}   {}'.format(task, tasks[task][1]))
    else:
        # D not refactor with an "except KeyError" here, or you will end up in hiding errors
        if task not in tasks:
            abort('Unknown command "{}". Type "reyns help" for a list of available commands'.format(task))
        else:
            tasks[task][0](*argv, **kwargs)

    # Output cleareness
    if not running_on_windows() and ('jsonout' not in kwargs) or ('jsonout' in kwargs and kwargs['jsonout']==False):
        print('')    


