
import os
import sys
import datetime
import subprocess
from collections import namedtuple

def shell(command, interactive=False):
    '''Execute a command in the shell. By default prints everything. If the capture switch is set,
    then it returns a namedtuple with stdout, stderr, and exit code.'''
    
    if interactive:
        exit_code = subprocess.call(command, shell=True)
        if exit_code == 0:
            return True
        else:
            return False
 
    process          = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (stdout, stderr) = process.communicate()
    exit_code        = process.wait()

    # Convert to str (Python 3)
    stdout = stdout.decode(encoding='UTF-8')
    stderr = stderr.decode(encoding='UTF-8')

    # Output namedtuple
    Output = namedtuple('Output', 'stdout stderr exit_code')

    # Return
    return Output(stdout, stderr, exit_code)


prestartup_scripts_path='/prestartup'
def sorted_ls(path):
    mtime = lambda f: os.stat(os.path.join(path, f)).st_mtime
    return list(sorted(os.listdir(path), key=mtime))

for item in sorted_ls(prestartup_scripts_path):
    if item.endswith('.sh'):
        
        # Execute this startup script
        print('[INFO] Executing prestartup script "{}"...'.format(item))
        script = prestartup_scripts_path+'/'+item

        # Use bash and not chmod + execute, see https://github.com/moby/moby/issues/9547
        out = shell('bash {}'.format(script))

        # Set date
        date_str = str(datetime.datetime.now()).split('.')[0]

        # Print and log stdout and stderr
        for line in out.stdout.strip().split('\n'):
            print(' out: {}'.format(line))
        
        #try:
        #    with open('/var/log/reyns/{}.stdout.log'.format(item), 'a') as stdout_file:
        #        stdout_file.write('\n ======== {} ========\n'.format(date_str))
        #        stdout_file.write(out.stdout)
        #except Exception as e:
        #    print('[ERROR] Cannot write stdout to file ({}: {}).'.format(e.__class__.__name__, e))

        for line in out.stderr.strip().split('\n'):
            print(' err: {}'.format(line))
        
        #try:
        #    with open('/var/log/reyns/{}.stderr.log'.format(item), 'a') as stderr_file:
        #        stderr_file.write('\n ======== {} ========\n'.format(date_str))
        #        stderr_file.write(out.stderr)
        #except Exception as e:
        #    print('[ERROR] Cannot write stderr to file ({}: {}).'.format(e.__class__.__name__, e))
        
        # Handle error in the startup script
        if out.exit_code:
            #print('[ERROR] Exit code "{}" for "{}", check log in /var/log/reyns/{}.stderr.log'.format(out.exit_code, item, item))            
            print('[ERROR] Exit code "{}" for "{}"'.format(out.exit_code, item))            

            # Exit with error code 1
            sys.exit(1)


        






















