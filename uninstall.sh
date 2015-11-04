#!/bin/bash

function uninstall_as_root {
                   echo 'Uninstalling as root...'
                   sudo rm -rf /usr/share/DockerOps && sudo rm /usr/local/bin/dockerops
                } 


function uninstall_as_user {
                   echo 'Uninstalling for user...'
                   rm  $HOME/bin/dockerops
                   rm -rf $HOME/.DockerOps
                }

               
if [ "$1" == "user" ]; then
    uninstall_as_user
    exit 0
fi


if [ "$1" == "root" ]; then
    uninstall_as_root
    exit 0
fi

echo ""
read -p "Was installation made for this user only? [y/n] "  -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]
then    
    uninstall_as_user
elif [[ $REPLY =~ ^[Nn]$ ]]
then   
    uninstall_as_root
else
    echo "Doing nothing."
fi

exit 0

