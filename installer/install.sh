#!/usr/bin/env bash

# ------------------------------------------------------------------------------------------------------------------------------------------------- #
# --                                                 ConsolePi Installation Script Stage 1                                                       -- #
# --  Wade Wells - Jul, 2019                                                                                                                     -- #
# --    report any issues/bugs on github or fork-fix and submit a PR                                                                             -- #
# --                                                                                                                                             -- #
# --  This script aims to automate the installation of ConsolePi.                                                                                -- #
# --  For manual setup instructions and more detail visit https://github.com/Pack3tL0ss/ConsolePi                                                -- #
# --                                                                                                                                             -- #
# --------------------------------------------------------------------------------------------------------------------------------------------------#

branch="master"

get_common() {
    wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/${branch}/installer/common.sh -O /tmp/common.sh
    . /tmp/common.sh
    [[ $? -gt 0 ]] && echo "FATAL ERROR: Unable to import common.sh Exiting" && exit 1
    [ -f /tmp/common.sh ] && rm /tmp/common.sh
    header 1>/dev/null
}

remove_first_boot() {
    #IF first boot was enabled by image creator script - remove it
    process="Remove exec on first-boot"
    sudo sed -i "s#consolepi-install##g" /home/pi/.bashrc
    grep -q consolepi-install /home/pi/.bashrc && 
        logit "Failed to remove first-boot verify /etc/rc.local" "WARNING"
}

get_pi_details() {
    # Collect some details about the Pi for diagnostic if an issue is reported
    process="Collect Pi Details"
    logit "$(get_pi_info)"
    unset process
}


do_apt_update() {
    header
    process="Update/Upgrade ConsolePi (apt)"
    logit "Update Sources"
    # Only update if initial install (no install.log) or if last update was not today
    if [[ ! -f "${final_log}" ]] || [[ ! $(ls -l --full-time /var/cache/apt/pkgcache.bin | cut -d' ' -f6) == $(echo $(date +"%Y-%m-%d")) ]]; then
        sudo apt-get update 1>/dev/null 2>> $log_file && logit "Update Successful" || logit "FAILED to Update" "ERROR"
    else
        logit "Skipping Source Update - Already Updated today"
    fi
    
    logit "Upgrading ConsolePi via apt. This may take a while"
    sudo apt-get -y upgrade 1>/dev/null 2>> $log_file && logit "Upgrade Successful" || logit "FAILED to Upgrade" "ERROR"
    
    logit "Performing dist-upgrade"
    sudo apt-get -y dist-upgrade 1>/dev/null 2>> $log_file && logit "dist-upgrade Successful" || logit "FAILED dist-upgrade" "WARNING"

    logit "Tidying up (autoremove)"
    apt-get -y autoremove 1>/dev/null 2>> $log_file && logit "Everything is tidy now" || logit "apt-get autoremove FAILED" "WARNING"
        
    logit "Installing git via apt"
    apt-get -y install git 1>/dev/null 2>> $log_file && logit "git install/upgraded Successful" || logit "git install/upgrade FAILED to install" "ERROR"
    logit "Process Complete"
    unset process
}

# Process Changes that are required prior to git pull when doing upgrade
pre_git_prep() {
    if $upgrade; then

        # remove old bluemenu.sh script replaced with consolepi-menu.py
        process="ConsolePi-Upgrade-Prep (refactor bluemenu.sh)"
        if [[ -f /etc/ConsolePi/src/bluemenu.sh ]]; then 
            rm /etc/ConsolePi/src/bluemenu.sh &&
                logit "Removed old menu script will be replaced during pull" ||
                    logit "ERROR Found old menu script but unable to remove (/etc/ConsolePi/src/bluemenu.sh)" "WARNING"
        fi
        # Remove old symlink if it exists
        process="ConsolePi-Upgrade-Prep (remove symlink consolepi-menu)"
        if [[ -L /usr/local/bin/consolepi-menu ]]; then
            unlink /usr/local/bin/consolepi-menu &&
                logit "Removed old consolepi-menu symlink will replace during upgade" ||
                    logit "ERROR Unable to remove old consolepi-menu symlink verify it should link to file in src dir" "WARNING"
        fi
        # Remove old launch file if it exists
        process="ConsolePi-Upgrade-Prep (remove consolepi-menu quick-launch file)"
        if [[ -f /usr/local/bin/consolepi-menu ]]; then
            rm /usr/local/bin/consolepi-menu &&
                logit "Removed old consolepi-menu quick-launch file will replace during upgade" ||
                    logit "ERROR Unable to remove old consolepi-menu quick-launch file" "WARNING"
        fi
    fi

    process="ConsolePi-Upgrade-Prep (create consolepi group)"
    for user in pi; do
        if [[ ! $(groups $user) == *"consolepi"* ]]; then
            if ! $(grep -q consolepi /etc/group); then 
                sudo groupadd consolepi && 
                logit "Added consolepi group" || 
                logit "Error adding consolepi group" "WARNING"
            else
                logit "consolepi group already exists"
            fi
            sudo usermod -a -G consolepi $user && 
                logit "Added ${user} user to consolepi group" || 
                    logit "Error adding ${user} user to consolepi group" "WARNING"
        else
            logit "all good ${user} user already belongs to consolepi group"
        fi
    done
    unset process

    if [ -f $cloud_cache ]; then
        process="ConsolePi-Upgrade-Prep (ensure cache owned by consolepi group)"
        group=$(stat -c '%G' $cloud_cache)
        if [ ! $group == "consolepi" ]; then
            sudo chgrp consolepi $cloud_cache 2>> $log_file &&
                logit "Successfully Changed cloud cache group" ||
                logit "Failed to Change cloud cache group" "WARNING"
        else
            logit "Cloud Cache ownership already OK"
        fi
        unset process
    fi
}

git_ConsolePi() {
    process="git Clone/Update ConsolePi"
    cd "/etc"
    if [ ! -d $consolepi_dir ]; then 
        logit "Clean Install git clone ConsolePi"
        git clone "${consolepi_source}" 1>/dev/null 2>> $log_file && logit "ConsolePi clone Success" || logit "Failed to Clone ConsolePi" "ERROR"
    else
        cd $consolepi_dir
        logit "Directory exists Updating ConsolePi via git"
        git pull 1>/dev/null 2>> $log_file && 
            logit "ConsolePi update/pull Success" || logit "Failed to update/pull ConsolePi" "ERROR"
    fi
    [[ ! -d $bak_dir ]] && sudo mkdir $bak_dir
    unset process
}

do_pyvenv() {
    process="Prepare/Check Python venv"
    logit "$process - Starting"

    # -- Check that git pull didn't bork venv ~ I don't think I handled the removal of venv from git properly seems to break things if it was already installed --
    if [ -d ${consolepi_dir}venv ] && [ ! -x ${consolepi_dir}venv/bin/python3 ]; then
        sudo mv ${consolepi_dir}venv $bak_dir && logit "existing venv found, moved to bak, new venv will be created (it is OK to delete anything in bak)"
    fi

    # -- Ensure python3-pip is installed --
    if [[ ! $(dpkg -l python3-pip 2>/dev/null| tail -1 |cut -d" " -f1) == "ii" ]]; then
        sudo apt-get install -y python3-pip 1>/dev/null 2>> $log_file && 
            logit "Success - Install python3-pip" ||
            logit "Error - installing Python3-pip" "ERROR"
    fi
    
    if [ ! -d ${consolepi_dir}venv ]; then
        # -- Ensure python3 virtualenv is installed --
        venv_ver=$(sudo python3 -m pip list --format columns | grep virtualenv | awk '{print $2}')
        if [ -z $venv_ver ]; then
            logit "python virtualenv not installed... installing"
            sudo python3 -m pip install virtualenv 1>/dev/null 2>> $log_file && 
                logit "Success - Install virtualenv" ||
                logit "Error - installing virtualenv" "ERROR"
        else
            logit "python virtualenv v${venv_ver} installed"
        fi

        # -- Create ConsolePi venv --
        logit "Creating ConsolePi virtualenv"
        sudo python3 -m virtualenv ${consolepi_dir}venv 1>/dev/null 2>> $log_file && 
            logit "Success - Creating ConsolePi virtualenv" ||
            logit "Error - Creating ConsolePi virtualenv" "ERROR"
    else
        logit "${consolepi_dir}venv directory already exists"
    fi

    if $upgrade; then
        # -- *Upgrade Only* update pip to current --
        logit "Upgrade pip"
        sudo ${consolepi_dir}venv/bin/python3 -m pip install --upgrade pip 1>/dev/null 2>> $log_file &&
            logit "Success - pip upgrade" ||
            logit "WARNING - pip upgrade returned error" "WARNING"
    fi

    # -- *Always* update venv packages based on requirements file --
    logit "pip install/upgrade ConsolePi requirements - This can take some time."
    sudo ${consolepi_dir}venv/bin/python3 -m pip install --upgrade -r ${consolepi_dir}installer/requirements.txt 1>/dev/null 2>> $log_file &&
        logit "Success - pip install/upgrade ConsolePi requirements" ||
        logit "Error - pip install/upgrade ConsolePi requirements" "ERROR"

    # -- temporary until I have consolepi module on pypi --
    logit "moving consolepi python module into venv site-packages"
    python_ver=$(ls -l /etc/ConsolePi/venv/lib | grep python3 |  awk '{print $9}')
    sudo cp -R ${src_dir}PyConsolePi/. ${consolepi_dir}venv/lib/${python_ver}/site-packages/consolepi 2>> $log_file &&
    # sudo cp -r ${src_dir}PyConsolePi ${consolepi_dir}venv/lib/python3*/site-packages 2>> $log_file &&
        logit "Success - moving consolepi python module into venv site-packages" ||
        logit "Error - moving consolepi python module into venv site-packages" "ERROR"

    unset process
}

# Configure ConsolePi logging directory and logrotate
do_logging() {
    process="Configure Logging"
    logit "Configure Logging in /var/log/ConsolePi - Other ConsolePi functions log to syslog"
    
    # Create /var/log/ConsolePi dir if it doesn't exist
    if [[ ! -d "/var/log/ConsolePi" ]]; then
        sudo mkdir /var/log/ConsolePi 1>/dev/null 2>> $log_file || logit "Failed to create Log Directory"
    fi

    # Create Log Files
    touch /var/log/ConsolePi/ovpn.log || logit "Failed to create OpenVPN log file" "WARNING"
    touch /var/log/ConsolePi/push_response.log || logit "Failed to create PushBullet log file" "WARNING"
    touch /var/log/ConsolePi/cloud.log || logit "Failed to create cloud log file" "WARNING"
    touch /var/log/ConsolePi/install.log || logit "Failed to create install log file" "WARNING"

    # Update permissions
    sudo chgrp consolepi /var/log/ConsolePi/* || logit "Failed to update group for log file" "WARNING"
    sudo chmod g+w /var/log/ConsolePi/* || logit "Failed to update group write privs" "WARNING"

    # move installer log from temp to it's final location
    if ! $upgrade; then
        log_file=$final_log
        cat $tmp_log >> $log_file
        rm $tmp_log
    else
        if [ -f $tmp_log ]; then 
            echo "ERROR: tmp log found when it should not have existed" | tee -a $final_log
            echo "-------------------------------- contents of leftover tmp log --------------------------------" >> $final_log
            cat $tmp_log >> $final_log
            echo "------------------------------ end contents of leftover tmp log ------------------------------" >> $final_log
            rm $tmp_log
        fi
    fi
   
    file_diff_update "${src_dir}ConsolePi.logrotate" "/etc/logrotate.d/ConsolePi"
    unset process
}

get_install2() {
    if [ -f "${consolepi_dir}installer/install2.sh" ]; then
        . "${consolepi_dir}installer/install2.sh"
    else
        echo "FATAL ERROR install2.sh not found exiting"
        exit 1
    fi
}

main() {
    script_iam=`whoami`
    if [ "${script_iam}" = "root" ]; then
        get_common              # get and import common functions script
        get_pi_details          # Collect some version info for logging
        remove_first_boot       # if autolaunch install is configured remove
        do_apt_update           # apt-get update the pi
        pre_git_prep            # process upgrade tasks required prior to git pull
        git_ConsolePi            # git ConsolePi
        do_pyvenv               # build python3 venv for ConsolePi
        do_logging              # Configure logging and rotation
        get_install2            # get and import install2 functions
        install2_main           # Kick off install2 functions
    else
      echo 'Script should be ran as root. exiting.'
    fi
}

main