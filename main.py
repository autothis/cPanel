#!/usr/bin/env python3

"""
Script Name: cpanel-backups.py
Description:
    This script handles:
        - Backing up specific or all cPanel accounts using the cmove cPanel Script.
        - Required free disk space estimation
        - Managing Retention for backup files
        - Reporting (Success/Fail and file changes due to Retention)
    It is expected to be run as a cron job, or through other scheduled based execution platforms (Ansible AWX etc...)

    Script Arguments:
        "--accounts"        # cPanel Accounts to be backedup. Comma separated list containing one or more cPanel accounts.  Can specify 'all' to backup all accounts.
        "--workingdir"      # This is where the script will store the tar.gz as it is created, and will be kept until a verified transfer to the backup location is compelted.  Defaults to /home if not specified.
        "--retention"       # This is the number of backups to be kept - it is NOT days or weeks.
        "--email"           # Email address to receive notifications.
        "--smtpserver"      # SMTP server responsible for sending notifications.
        "--smtpuser"        # SMTP server authentication username.
        "--smtppassword"    # SMTP server authentication password.
        "--destination"     # Destination for cPanel backup files.
        "--excludeaccounts" # List of accounts to exclude, when using all option.

    Example Script Execution:
        "cpanel-backup.py --accounts all --workingdir '/tmp' --retention '7' --email 'cpaneladmin@example.com' --smtpserver 'smtp.example.com' --smtpuser 'smtpuser' --smtppassword 'smtpP@ssw0rd' --destination '/backupdrive' --excludeaccounts Michael"
            or
        "cpanel-backup.py --accounts 'user1' --workingdir '/tmp' --retention '7' --email 'cpaneladmin@example.com' --smtpserver 'smtp.example.com' --smtpuser 'smtpuser' --smtppassword 'smtpP@ssw0rd' --destination '/backupdrive'"
            or
        "cpanel-backup.py --accounts Michael Josh \
            --workingdir '/tmp' \
            --retention '7' \
            --email 'cpaneladmin@example.com' \
            --smtpserver 'smtp.example.com' \
            --smtpuser 'smtpuser' \
            --smtppassword 'smtpP@ssw0rd' \
            --destination '/backupdrive' \
            --excludeaccounts randy_randleman \
            /"

    Features to be added:
        - Authenticated File transfer Support: FTP etc...
        - Retention only mode:  If you change the retention to a lower number, the script can be run to clean up files without running backups.
        - Split functions into separate file to make main code easier to read.
        - Backup Processing:
            simultaneous: Script will start on the next cpanel backup, while the previous is still being uploaded.
            sequential: There is not enough disk space to hold all the backups locally, so backup and then transfer will need to complete, before the next cpanel account backup can start.

Author: Perrynaise
Date: 2025-01-08 (Jan 8th 2025)

"""

# Import Modules
import sys
import os
import subprocess
import argparse
import json
import shutil

# Import Functions from 'functions.py'
import functions

####################################################################################################################################################
################################################# Process Parsed Arguments and Initalize Variables #################################################
####################################################################################################################################################

# Manually Defined Variables - These will be individually overriden if matching argument is passed from commandline.
#cpanel_backup_accounts = ["Michael", "Josh"]                           # One or more cPanel Accounts to be backedup. CASE SENSITIVE!  Can specify 'all' to backup all accounts.
cpanel_backup_accounts = ["all"]                           # One or more cPanel Accounts to be backedup. CASE SENSITIVE!  Can specify 'all' to backup all accounts.
cpanel_backup_working_directory = "/home"                               # This is where the script will store the tar.gz as it is created, and will be kept until a verified transfer to the backup location is completed.  Defaults to /home if not specified.
#cpanel_backup_retention = "7"                                          # This is the number of backups to be kept - it is NOT days or weeks.
#cpanel_backup_email = "cpaneladmin@example.com"                        # Email address to receive notifications.
#cpanel_backup_smtp_server = "smtp@example.com"                         # SMTP server responsible for sending notifications.
#cpanel_backup_smtp_user = "smtpusername"                               # SMTP server authentication username.
#cpanel_backup_smtp_password = "smtppassw0rd"                           # SMTP server authentication password.
#cpanel_backup_destination = "/dedicated_backup_drive/cpanel_backups"   # Destination for cPanel backup files.
#cpanel_backup_destination = "/home"   # Destination for cPanel backup files.
#cpanel_backup_exclude_accounts = "randy_randleman"                     # List of accounts to exclude, when using all option.

# Variables to keep track of - List of variables used in this script, and what they are used for.
cpanel_backup_running_size = ""     # This is the running total for backup file sizes, to be provided in email notification to help with capacity planning.

# Import Arguments
parser=argparse.ArgumentParser()
parser.add_argument("--accounts", help="cPanel Accounts to be backedup. Comma separated list containing one or more cPanel accounts.  Can specify 'all' to backup all accounts.")
#parser.add_argument('--accounts', type=str, nargs='+', help="One or more cPanel Accounts to be backedup. CASE SENSITIVE!  Can specify 'all' to backup all accounts.", required=True)
parser.add_argument("--workingdir", help="This is where the script will store the tar.gz as it is created, and will be kept until a verified transfer to the backup location is compelted.  Defaults to /home if not specified.")
parser.add_argument("--retention", help="This is the number of backups to be kept - it is NOT days or weeks")
parser.add_argument("--email", help="Email address to receive notifications")
parser.add_argument("--smtpserver", help="SMTP server responsible for sending notifications")
parser.add_argument("--smtpuser", help="SMTP server authentication username")
parser.add_argument("--smtppassword", help="SMTP server authentication password")
parser.add_argument("--destination", help="Destination for cPanel backup files")
#parser.add_argument("--destination", help="Destination for cPanel backup files", required=True)
parser.add_argument("--excludeaccounts", type=str, nargs='+', help="List of accounts to exclude, when using all option")
args=parser.parse_args()

# Set argument to variable mapping
argument_mappings = {
    "accounts": "cpanel_backup_accounts",
    "workingdir": "cpanel_backup_working_directory",
    "retention": "cpanel_backup_retention",
    "email": "cpanel_backup_email",
    "smtpserver": "cpanel_backup_smtp_server",
    "smtpuser": "cpanel_backup_smtp_user",
    "smtppassword": "cpanel_backup_smtp_password",
    "destination": "cpanel_backup_destination",
    "excludeaccounts": "cpanel_backup_exclude_accounts",
}

# Iterate through argument to variable mappings and update variable if argument is provided.
for argument_mapping, variable_name in argument_mappings.items():
    if getattr(args, argument_mapping) is not None:
        globals()[variable_name] = getattr(args, argument_name)

####################################################################################################################################################
####################################################### Get Filtered List of cPanel Accounts #######################################################
####################################################################################################################################################

# Retrieve List of all cPanel Accounts
all_cpanel_accounts = functions.CpanelListAllAccounts()
print("###################### All cPanel Accounts ######################")
print(all_cpanel_accounts)

# Get cPanel Account Data and Filter for selected Accounts
filtered_cpanel_accounts = functions.CpanelAccountsFilter(all_cpanel_accounts, cpanel_backup_accounts)
print("###################### cPanel Filtered Accounts ######################")
print(filtered_cpanel_accounts)

####################################################################################################################################################
########################################################### Process Storage Requirements ###########################################################
####################################################################################################################################################

# Get cPanel account size estimate
#cpanel_account_size_esitmate = functions.CpanelAccountSizeEstimateMB(filtered_cpanel_accounts)
#print("###################### cPanel Account Size Estimate ######################")
#print(cpanel_account_size_esitmate)

# Retrieve Working Dir free space
#cpanel_free_space = functions.GetFreeSpaceLocalDisk(cpanel_backup_destination)
#print("###################### cPanel Free Space ######################")
#print(cpanel_free_space)

# Calcuate if cPanel backups and FTP transfer can be done simultaneously or if it needs to be done sequentially (based on free space)
#if cpanel_account_size_esitmate["total"] > cpanel_free_space["free"]:
#    cpanel_backup_processing = "simultaneous"
#if cpanel_account_size_esitmate["biggest"]["sizemb"] > cpanel_free_space["free"]:
#    cpanel_backup_processing = "sequential"
#print(cpanel_backup_processing)

####################################################################################################################################################
############################################################## Backup cPanel Accounts ##############################################################
####################################################################################################################################################

# for each account backup, check for backup errors, apply retention, transfer to destination, confirm successful transfer, clean up working dir
for cpanel_account in filtered_cpanel_accounts["data"]["acct"]:

    #Estimate cPanel Account Disk Space Requirements
    cpanel_backup_workingdir_free_space_buffer_mb = 1024 #This is how much free space ontop of the cpanel estimated size you require, for the backup to run
    cpanel_backup_required_space_mb = ((functions.ConvertToMB(cpanel_account["diskused"]) * 2) + cpanel_backup_workingdir_free_space_buffer_mb) 

    #Check if Working Directory has enough free space to fit this cPanel Account's estimated size
    if cpanel_backup_required_space_mb > (functions.GetFreeSpaceLocalDisk(cpanel_backup_working_directory))["free"]:
        #cpanel_account_backup_result["result"] = "Not enough free space on ()"#error and exit
        cpanel_backup_result = {}
        cpanel_backup_result["account"] = cpanel_account['user']
        cpanel_backup_result["est_size_mb"] = cpanel_account['diskused']
        cpanel_backup_result["required_free_mb"] = cpanel_backup_required_space_mb
        cpanel_backup_result["working_directory_free_mb"] = (functions.GetFreeSpaceLocalDisk(cpanel_backup_working_directory))['free']
        cpanel_backup_result["result"] = "failed"
        cpanel_backup_result["info"] = f"There is not enough free space on: {cpanel_backup_working_directory} for cPanel Account: {cpanel_account['user']}"
        
        #print(f"\033[31mThere is not enough free space on {cpanel_backup_working_directory} for cPanel Account: {cpanel_account['user']}\033[0m")
        #print(f"\tRequired Free Space(MB): {cpanel_backup_required_space}")
        #print(f"\tWorking Directory Free Space(MB): {(functions.GetFreeSpaceLocalDisk(cpanel_backup_working_directory))['free']}")
        #print(f"\tAdditional Free Space Required(MB): {((cpanel_backup_required_space) - (functions.GetFreeSpaceLocalDisk(cpanel_backup_working_directory))['free'])}")
    else:
        print(f"There is enough free space on {cpanel_backup_working_directory} for cPanel Account: {cpanel_account['user']}")
        print(f"\tRequired Free Space(MB): {cpanel_backup_required_space_mb}")
        print(f"\tWorking Directory Free Space(MB): {(functions.GetFreeSpaceLocalDisk(cpanel_backup_working_directory))['free']}")

        #backup account to workingdir
        #####/usr/local/cpanel/scripts/pkgacct eatingsecretscom /home/backuptest
        #apply retention for that accounts backups
        #####Will need to ftp, list backups matching user, make sure there are at least as many as there should be, if there are identify and delete the oldest
        #transfer to ftp destination
        #####Will need to ftp, copy file
        #confirm successful transfer
        #####Will need to ftp, and somehow verify file.... might be as little as confirming the file is there
        #clean up workingdir
        #####Delete files in the cpanel_backup_working_directory related to cpanel_account['user']
        #log results to report
        #####Report User, Uncompressed Size, Compressed Size, 
