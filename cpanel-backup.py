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

# Manually Defined Variables - These will be individually overriden if matching argument is passed from commandline.
#cpanel_backup_accounts = ["Michael", "Josh"]                           # One or more cPanel Accounts to be backedup. CASE SENSITIVE!  Can specify 'all' to backup all accounts.
cpanel_backup_accounts = ["all"]                           # One or more cPanel Accounts to be backedup. CASE SENSITIVE!  Can specify 'all' to backup all accounts.
#cpanel_backup_working_directory = "/tmp"                               # This is where the script will store the tar.gz as it is created, and will be kept until a verified transfer to the backup location is completed.  Defaults to /home if not specified.
#cpanel_backup_retention = "7"                                          # This is the number of backups to be kept - it is NOT days or weeks.
#cpanel_backup_email = "cpaneladmin@example.com"                        # Email address to receive notifications.
#cpanel_backup_smtp_server = "smtp@example.com"                         # SMTP server responsible for sending notifications.
#cpanel_backup_smtp_user = "smtpusername"                               # SMTP server authentication username.
#cpanel_backup_smtp_password = "smtppassw0rd"                           # SMTP server authentication password.
#cpanel_backup_destination = "/dedicated_backup_drive/cpanel_backups"   # Destination for cPanel backup files.
cpanel_backup_destination = "/home"   # Destination for cPanel backup files.
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

# Retreive a Account information from WHM API
def cpanel_list_all_accounts():
    try:
        # Retreive Account Information using 'whmapi1' command
        result = subprocess.run(
            args = ["/usr/local/cpanel/bin/whmapi1", "--output=json", "listaccts"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Create JSON formatted response variable
        response = json.loads(result.stdout)
        
        # If whmapi1 response "result" is 0 raise error
        if response["metadata"]["result"] ==0:
            raise ValueError("whmapi1 query failed", response["metadata"]["reason"])
            # response["metadata"]["result"] alue of 0 is a failure, 1 is a success
        return response
    except Exception as e:
        # Handle unexpected exceptions
        print(f"An unexpected error occurred: {e}")
        return None

# Convert Values formatted '^\d+[A-Z]$' to Megabytes
def convert_to_mb(value):
    if value.endswith("K"):
        # Convert KB to MB
        return int(value.strip('K')) / 1024
    elif value.endswith("M"):
        # It's already in MB
        return int(value.strip('M'))
    elif value.endswith("G"):
        # Convert GB to MB
        return int(value.strip('G')) * 1024
    else:
        return 0  # If the value is not recognized

# Filter cPanel Accounts
def cpanel_accounts_filter(cpanel_accounts_list):
    try:
        # Verify cpanel_accounts_list variable - check if 'data' and 'acct' keys exist
        if not cpanel_accounts_list or "data" not in cpanel_accounts_list or "acct" not in cpanel_accounts_list["data"]:
            raise ValueError("Invalid response structure: 'data' or 'acct' keys are missing.")
        
    # Handle Exceptions
    except Exception as e:
        print(f"Error fetching or processing accounts: {e}")
        return 0
    
    try:
        if cpanel_backup_accounts[0] != 'all':
        #if cpanel_backup_accounts[0].lower() != 'all':
            # Initalize a Empty Variable to Populate with Filtered Users
            cpanel_users_filtered = []
            
            for account in cpanel_accounts_list["data"]["acct"]:
                for cpanel_user in cpanel_backup_accounts:
                    if account["user"] == cpanel_user:
                    #if account["user"].lower() == cpanel_user.lower():
                        cpanel_users_filtered.append(account)
        else:
            cpanel_users_filtered = cpanel_accounts_list
        return cpanel_users_filtered
    # Handle Exceptions
    except KeyError as e:
        print(f"Skipping account due to missing 'diskused' field: {e}")

# Add cPanel users disk usage together to estimate uncompressed backup size
def cpanel_account_size_estimate_mb(filtered_cpanel_accounts):
    try:
        # Initalize cPanel Accounts Total Size Variable
        cpanel_uncompressed_size_mb = {}
        cpanel_uncompressed_size_mb["total"] = 0
        cpanel_uncompressed_size_mb["biggest"] = {}
        cpanel_uncompressed_size_mb["biggest"]["user"] = ""
        cpanel_uncompressed_size_mb["biggest"]["sizemb"] = 0
        
        # Loop cPanel Accounts
        for account in filtered_cpanel_accounts["data"]["acct"]:
            try:
                # Make sure 'diskused' is valid
                if "diskused" not in account:
                    raise KeyError(f"Account {account} 'diskused' field is empty")
                    
                # Convert 'diskused' to Megabytes
                disk_used_mb = convert_to_mb(account["diskused"])
                
                # Add to cPanel total size
                cpanel_uncompressed_size_mb["total"] += disk_used_mb
                
                # Compare individual user size, only keep the largest
                if disk_used_mb > cpanel_uncompressed_size_mb["biggest"]["sizemb"]:
                    cpanel_uncompressed_size_mb["biggest"]["user"] = account["user"]
                    cpanel_uncompressed_size_mb["biggest"]["sizemb"] = disk_used_mb
                
            # Handle Exceptions
            except KeyError as e:
                print(f"Skipping account due to missing 'diskused' field: {e}")
            except ValueError as e:
                print(f"Skipping account due to invalid diskused value: {e}")
            except Exception as e:
                print(f"Unexpected error while processing account {account}: {e}")
       
        # Return Results
        return cpanel_uncompressed_size_mb
        
    # Handle Exceptions
    except KeyError as e:
        print(f"Skipping due to missing 'diskused' field: {e}")

# Get Free Space (Local Disk)
class DirectoryPathError(Exception):
    def __init__(self, message="Provided directory is not accessible"):
        self.message = message
        super().__init__(self.message)

def get_free_space_local_disk(directory_path):
    try:
        # Make sure directory_path exists
        if os.path.isdir(directory_path):
            
            # Get free space and store in variable free_space
            free_space = {}
            free_space["total"], free_space["used"],free_space["free"] = shutil.disk_usage(directory_path)
            
            free_space["total"] = free_space["total"] //(1024**2)
            free_space["used"] = free_space["used"] //(1024**2)
            free_space["free"] = free_space["free"] //(1024**2)
            
            # Return Results
            return free_space
        else:
            raise DirectoryPathError(f"{directory_path}")
            
    # Handle Exceptions
    except DirectoryPathError as e:
        print(f"Error: Provided directory is not accessible: {e}")

# Get cPanel Account Data and Filter for selected Accounts
filtered_cpanel_accounts = cpanel_accounts_filter(cpanel_list_all_accounts())
#print(filtered_cpanel_accounts)

# Get cPanel account size estimate
cpanel_account_size_esitmate = cpanel_account_size_estimate_mb(filtered_cpanel_accounts)
#print(cpanel_account_size_esitmate)

# Check if Working Dir has enough space to create backup file estimated size
get_free_space_local_disk(cpanel_backup_destination)
# for each account, compare estimated size to free space

# Check to see if Destination has enough free space to store backup file estimated size

# for each account backup, check for backup errors, apply retention, transfer to destination, confirm successful transfer, clean up working dir
