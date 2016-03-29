#!/bin/bash

function install_as_root {
                           echo ''
                           echo 'Installing as root...'
                           echo ''
                           sudo cp -a ../DockerOps /usr/share/ && sudo ln -s /usr/share/DockerOps/dockerops /usr/local/bin/dockerops
                           echo 'Building base containers on top of Ubuntu 14.04... (in the next versions you will be able to choose the OS)'
                           fab init
                           echo 'Done.'
                         }


function install_as_user {
                           echo ''
                           echo "Installing for user \"$USER\"..."
                           mkdir -p $HOME/bin/
                           rm -f $HOME/bin/dockerops
                           rm -rf $HOME/.DockerOps
                           ln -s $HOME/.DockerOps/dockerops $HOME/bin/dockerops
                           cp -a ../DockerOps $HOME/.DockerOps
                           echo ''
                           echo 'Building base containers on top of Ubuntu 14.04... (in the next versions you will be able to choose the OS)'
                           fab init
                           echo 'Done. On most of the Linux distributions you have to open a new shell to have $HOME/bin loaded'
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

