#!/bin/bash

function install_as_root {
                           echo ''
                           echo 'Installing as root...'
                           cd ..
                           sudo cp -a DockerOps /usr/share/ && sudo ln -s /usr/share/DockerOps/dockerops /usr/local/bin/dockerops
                         } 


function install_as_user {
                           echo ''
                           echo 'Installing for user...'
                           mkdir -p $HOME/bin/
                           rm -f $HOME/bin/dockerops
                           rm -rf $HOME/.DockerOps
                           ln -s $HOME/.DockerOps/dockerops $HOME/bin/dockerops
                           cd ..
                           cp -a DockerOps $HOME/.DockerOps
                           echo 'Done. On the majority of Linux distributions you have to open a new shell to hane $HOME/bin loaded'
                         }

               
if [ "$1" == "user" ]; then
    install_as_user
    exit 0
fi


if [ "$1" == "root" ]; then
    install_as_root
    exit 0
fi

echo ""
read -p "Install for this user only? [y/n] "  -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]
then   
    install_as_user
elif [[ $REPLY =~ ^[Nn]$ ]]   
then
    install_as_root
else
    echo "Doing nothing."
fi

exit 0

