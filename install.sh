#!/bin/bash

function install_as_root {
                           echo ''
                           echo 'Installing as root...'
                           echo ''
                           sudo rm -f /usr/local/bin/dockerops
                           sudo rm -rf /usr/share/DockerOps
                           sudo cp -a $PWD /usr/share/DockerOps
                           sudo ln -s /usr/share/DockerOps/dockerops /usr/local/bin/dockerops
                           echo 'Building...'
                           sudo fab init
                           echo 'Done.'
                         }


function install_as_user {
                           echo ''
                           echo "Installing for user \"$USER\"..."
                           mkdir -p $HOME/bin/
                           rm -f $HOME/bin/dockerops
                           rm -rf $HOME/.DockerOps
                           cp -a $PWD $HOME/.DockerOps
                           ln -s $HOME/.DockerOps/dockerops $HOME/bin/dockerops
                           echo ''
                           echo 'Building...'
                           fab init
                           echo 'Done. On most of the Linux distributions you have to open a new shell to have $HOME/bin loaded'
                         }

echo ""

# Check that docker is installed
if hash docker 2>/dev/null; then
    echo "[OK] Found Docker"
else
    echo "[ERROR] Missing Docker" 
    exit 1
fi

# Check that fab is installed
if hash fab 2>/dev/null; then
    echo "[OK] Found fabric package (fab command)"
else
    echo "[ERROR] Missing fabric package (fab command)"
    exit 1
fi


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

