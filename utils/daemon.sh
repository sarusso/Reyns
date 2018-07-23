#!/bin/bash

# Check we are in the right place
if [ ! -d ./services ]; then
    echo "You must run this script from the project's root folder."
    exit 1
fi

# Support vars
JUSTSTARTED=true
RECURSIVE=$1

# Log that we started the daemon
echo "Starting daemon..."

# Run setup
reyns setup

# Start daemon
echo "Started daemon @ $(date)"

# Check if this is the first run or a recursive run
if [[ "x$(echo $RECURSIVE | grep recursive | cut -d'=' -f2)" == "xTrue" ]] ; then
    echo "Recursive run, not starting the services."
else
    echo "First run, starting the services..."

    # Check on which branch we are
    BRANCH=$(git rev-parse --symbolic-full-name --abbrev-ref HEAD 2>&1)
    if [ ! $? -eq 0 ]; then
        echo $BRANCH
        echo "Error: could not obtain local branch at startup time. See output above."
        echo "Current time: $(date)"
    fi

    # Build "just in case", in particular for first run ever
    echo "Now building..."
    reyns build:all

    # If the above failed, try with no cache
	if [ ! $? -eq 0 ]; then
	    echo "Error in rebuilding services, now trying without cache..."
	    reyns build:all,cache=False
	    if [ ! $? -eq 0 ]; then
	        echo "Error: failed rebuilding services even without cache."
	        continue
	    fi
	fi

    # Check if there is a conf for this branch name
	if [[ -f $BRANCH.conf ]] ; then
	    echo "Using conf \"$BRANCH.conf\"."
	    RUN_CMD="reyns run:all,conf=$BRANCH"
	else
	    echo "Using default conf as no \"$BRANCH.conf\" has been found."
	    RUN_CMD="reyns run:all"
	fi

    # Clean before running
    reyns clean:all,force=True

    # Run
    $RUN_CMD
    if [ ! $? -eq 0 ]; then
        echo "Error: reyns run failed at startup time. See output above."
        echo "Current time: $(date)"
        echo "Current branch: $BRANCH"
        echo ""
        echo "I will now mark the forthcoming update process as \"unfinished\", which will"
        echo "trigger a new build and re-run as soon as the update check loop will start."
        touch .update_in_progress_flag
    fi
fi


# Start update loop
while true
do

    # Get date TODO: directly use $(date) in the code
    DATE=$(date)

    # Sleep before next iteration (if not just started)
    if [ "$JUSTSTARTED" = true ]; then

        JUSTSTARTED=false

        # Log that we started the update loop
        echo ""
        echo "Started update check loop @ $DATE"

    else
        sleep 60
    fi

    # Check on which branch we are
    BRANCH=$(git rev-parse --symbolic-full-name --abbrev-ref HEAD 2>&1)
    if [ ! $? -eq 0 ]; then
        echo $BRANCH
        echo "Error: could not obtain local branch. See output above."
        echo "Current time: $DATE"
        continue
    fi

    # Update from remote
    GIT_REMOTE=$(git remote -v update 2>&1)

    if [ ! $? -eq 0 ]; then
        echo $GIT_REMOTE
        echo "Error: could not check remote status. See output above."
        echo "Current time: $DATE"
        echo "Current branch: $BRANCH"
        continue
    fi

    # Check log diff within local and origin (remote)
    GIT_LOG=$(git log $BRANCH..origin/$BRANCH --oneline)

    # If an update was started and not completed, just force it
    if [ -f .update_in_progress_flag ]; then
        GIT_LOG="FORCED"
        echo "Detected unfinished update process, resuming it..."
    fi


    if [[ "x$GIT_LOG" == "x" ]] ; then

        # Remote has not changed. Do nothing
        :

    else

        # Remote has changed. Start update process
        echo "Remote changes detected"
        echo "Current time: $DATE"
        echo "Current branch: $BRANCH"
        echo "Starting the update process..."

        # Set update in progress flag
        touch .update_in_progress_flag

        # Pull changes from origin (remote)
        GIT_PULL=$(git pull 2>&1)

        # If pull failed abort
        if [ ! $? -eq 0 ]; then
            echo $GIT_PULL
            echo "Error: pull failed. See output above."
            continue
        fi

        # Run reyns setup, that will take care in turn of checking
        # Reyns version and of running project's setup.sh if present.
	    echo "Running setup"    
	    reyns setup

        # Re-build
        echo "Now building..."
        reyns build:all

        # If the above failed, try with no cache
        if [ ! $? -eq 0 ]; then
            echo "Error in rebuilding services, now trying without cache..."
            reyns build:all,cache=False
            if [ ! $? -eq 0 ]; then
                echo "Error: failed rebuilding services even without cache."
                continue
            fi
        fi

        # All good if we are here. Restart everything
        reyns clean:all,force=True

        # Check if there is a conf for this branch name
        if [[ -f $BRANCH.conf ]] ; then
            echo "Using conf \"$BRANCH.conf\"."
            RUN_CMD="reyns run:all,conf=$BRANCH"
        else
            echo "Using default conf as no \"$BRANCH.conf\" has been found."
            RUN_CMD="reyns run:all"
        fi

        $RUN_CMD
        if [ ! $? -eq 0 ]; then
            echo "Error: reyns run failed. See output above."
            continue
        fi

        # Remove update in progress flag
        rm .update_in_progress_flag

        # Load new daemon
        echo "Now loading new daemon..."
        exec reyns daemon:recursive=True
    fi

done
