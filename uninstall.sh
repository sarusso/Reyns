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


function uninstall_as_root {
                   echo 'Uninstalling as root...'
                   sudo rm -rf /usr/share/DockerOps && sudo rm /usr/local/bin/dockerops
                } 


function uninstall_as_user {
                   echo 'Uninstalling for this user...'

                   # Remove data files
                   rm -f $HOME/bin/dockerops # Older versions
                   rm -rf $HOME/.DockerOps

                   # Remove from bash_profile
                   if [ -f $HOME/.bash_profile ]; then
                       cp $HOME/.bash_profile $HOME/.bash_profile_backedup_by_DockerOps
                       awk '!/#BsKwKOabGH/' $HOME/.bash_profile > $HOME/.bash_profile
                   fi

                }

#----------------------------
# Set platform capabilities
#----------------------------

set_platform_capabilities


#----------------------------
# Handle command line args
#----------------------------
            
if [ "$1" == "user" ]; then
    uninstall_as_user
    exit 0
fi

if [ "$1" == "root" ]; then

    if [ "$ROOT_INSTALL_SUPPORTED" == "False" ]; then
        echo ""
        read -p "WARNING: it seems that root install was not possible on this platform. Proceed? [y/n] "  -r

        if [[ $REPLY =~ ^[Yy]$ ]]
        then
            uninstall_as_root
        elif [[ $REPLY =~ ^[Nn]$ ]]
        then
            echo "Cancelled."
        else
            echo "Doing nothing."
        fi
    else
        uninstall_as_root
    fi
    exit 0
fi


#----------------------------
# Main uninstall logic
#----------------------------

echo ""
if [ "$ROOT_INSTALL_SUPPORTED" == "False" ]; then
    echo "WARNING: it seems that root install was not possible on this platform."
else
    echo "NOTICE: by default, DockerOps is installed in user-space. For root uninstall, use \"./uninstall.sh root\"."
fi

echo ""
read -p "Proceed in uninstalling for this user only? [y/n] "  -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]
then    
    uninstall_as_user
elif [[ $REPLY =~ ^[Nn]$ ]]
then   
    echo "Cancelled."
else
    echo "Doing nothing."
fi

exit 0
