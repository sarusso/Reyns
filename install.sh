#!/bin/bash

ROOT_INSTALL_SUPPORTED="False"

function set_platform_capabilities {
                unameOut="$(uname -s)"
                case "${unameOut}" in
                    Linux*)     machine=Linux;;
                    Darwin*)    machine=Mac;;
                    CYGWIN*)    machine=Cygwin;;
                    MINGW*)     machine=MinGw;;
                    *)          machine="UNKNOWN:${unameOut}"
                esac
                
                if [ "${machine}" == "Linux" ]; then
                    ROOT_INSTALL_SUPPORTED="True"
                fi

                if [ "${machine}" == "Mac" ]; then
                    ROOT_INSTALL_SUPPORTED="True"
                fi                
                
                
                }


function install_as_root {
                           echo 'Installing as root...'
                           echo ''
                           sudo rm -f /usr/local/bin/dockerops
                           sudo rm -rf /usr/share/DockerOps
                           sudo cp -a $PWD /usr/share/DockerOps
                           sudo ln -s /usr/share/DockerOps/dockerops /usr/local/bin/dockerops
                           echo 'Done.'
                           echo ""
                         }


function install_as_user {
                           echo "Installing in \"$HOME\"..."
                           rm -f $HOME/bin/dockerops
                           rm -rf $HOME/.DockerOps
                           cp -a $PWD $HOME/.DockerOps

                           # Ensure .bash_profile exists for this user
                           if [ ! -f $HOME/.bash_profile ]; then
                               touch $HOME/.bash_profile
                           fi

                           TEST="`cat $HOME/.bash_profile | grep \"/.DockerOps/\"`"
                           if [ -z "$TEST" ]; then
                               echo "PATH=\$PATH:$HOME/.DockerOps/ && export PATH #BsKwKOabGH - Added by DockerOps, do not edit!" >> $HOME/.bash_profile
                           fi

                           echo "Done. Open a new Bash (login) shell for being able to use DockerOps."
                           echo ""
                         }

echo ""

#----------------------------
# Check Docker is installed
#----------------------------

if hash docker 2>/dev/null; then
    echo "[OK] Found Docker"
else
    echo "[ERROR] Missing Docker" 
    exit 1
fi


#----------------------------
# Check Fabric is installed
#----------------------------

if hash fab 2>/dev/null; then
    echo "[OK] Found Fabric package (fab command)"
else
    echo "[ERROR] Missing Fabric package (fab command)"
    exit 1
fi


#----------------------------
# Set platform capabilities
#----------------------------

set_platform_capabilities


#----------------------------
# Handle command line args
#----------------------------

if [ "$1" == "user" ]; then
    install_as_user
    exit 0
fi

if [ "$1" == "root" ]; then

    if [ "$ROOT_INSTALL_SUPPORTED" == "False" ]; then
        echo ""
        read -p "WARNING: it seems that root install is not possible on this platform. Proceed? [y/n] "  -r

        if [[ $REPLY =~ ^[Yy]$ ]]
        then
            install_as_root
        elif [[ $REPLY =~ ^[Nn]$ ]]
        then
            echo "Cancelled."
        else
            echo "Doing nothing."
        fi
    else
        install_as_root
    fi
    exit 0
fi


#----------------------------
# Main install logic
#----------------------------

echo ""
if [ "$ROOT_INSTALL_SUPPORTED" == "False" ]; then
    echo "WARNING: it seems that root install is not possible on this platform."
else
    echo "NOTICE: by default, DockerOps is installed in user-space. For root install, use \"./install.sh root\"."
fi


echo ""
read -p "Proceed in installing for this user only? [y/n] "  -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]
then
    install_as_user
elif [[ $REPLY =~ ^[Nn]$ ]]
then
    echo "Cancelled."
else
    echo "Doing nothing."
fi

exit 0
