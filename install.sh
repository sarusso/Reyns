#!/bin/bash

function install_as_root {
                           echo ''
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
                           echo ''
                           echo "Installing for user \"$USER\"..."
                           rm -f $HOME/bin/dockerops
                           rm -rf $HOME/.DockerOps
                           cp -a $PWD $HOME/.DockerOps

                           TEST="`cat /Users/ste/.bash_profile | grep \"/.DockerOps/\"`"
                           if [ -z "$TEST" ]; then
                               echo "PATH=\$PATH:$HOME/.DockerOps/" >> $HOME/.bash_profile
                               echo "export PATH" >> $HOME/.bash_profile
                           fi

                           echo "Done. Open a new (Bash) shell for being able to use DockerOps"
                           echo ""
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
    echo "[OK] Found Fabric package (fab command)"
else
    echo "[ERROR] Missing Fabric package (fab command)"
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

