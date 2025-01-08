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

Author: Perrynaise
Date: 2025-01-08 (Jan 8th 2025)

"""

# Import Modules
import sys
import subprocess
import argparse
import json

# Manually Defined Variables - These will be individually overriden if matching argument is passed from commandline.
#cpanel_backup_accounts = ["Michael", "Josh"]                           # One or more cPanel Accounts to be backedup. CASE SENSITIVE!  Can specify 'all' to backup all accounts.
#cpanel_backup_working_directory = "/tmp"                               # This is where the script will store the tar.gz as it is created, and will be kept until a verified transfer to the backup location is completed.  Defaults to /home if not specified.
#cpanel_backup_retention = "7"                                          # This is the number of backups to be kept - it is NOT days or weeks.
#cpanel_backup_email = "cpaneladmin@example.com"                        # Email address to receive notifications.
#cpanel_backup_smtp_server = "smtp@example.com"                         # SMTP server responsible for sending notifications.
#cpanel_backup_smtp_user = "smtpusername"                               # SMTP server authentication username.
#cpanel_backup_smtp_password = "smtppassw0rd"                           # SMTP server authentication password.
#cpanel_backup_destination = "/dedicated_backup_drive/cpanel_backups"   # Destination for cPanel backup files.
#cpanel_backup_exclude_accounts = "randy_randleman"                     # List of accounts to exclude, when using all option.

# Variables to keep track of - List of variables used in this script, and what they are used for.
cpanel_backup_running_size = ""     # This is the running total for backup file sizes, to be provided in email notification to help with capacity planning.

# Import Arguments
parser=argparse.ArgumentParser()
#parser.add_argument("--accounts", help="cPanel Accounts to be backedup. Comma separated list containing one or more cPanel accounts.  Can specify 'all' to backup all accounts.")
parser.add_argument('--accounts', type=str, nargs='+', help="One or more cPanel Accounts to be backedup. CASE SENSITIVE!  Can specify 'all' to backup all accounts.", required=True)
parser.add_argument("--workingdir", help="This is where the script will store the tar.gz as it is created, and will be kept until a verified transfer to the backup location is compelted.  Defaults to /home if not specified.")
parser.add_argument("--retention", help="This is the number of backups to be kept - it is NOT days or weeks")
parser.add_argument("--email", help="Email address to receive notifications")
parser.add_argument("--smtpserver", help="SMTP server responsible for sending notifications")
parser.add_argument("--smtpuser", help="SMTP server authentication username")
parser.add_argument("--smtppassword", help="SMTP server authentication password")
parser.add_argument("--destination", help="Destination for cPanel backup files", required=True)
parser.add_argument("--excludeaccounts", type=str, nargs='+', help="List of accounts to exclude, when using all option")
args=parser.parse_args()

# Set Variables using provided Arguments (if any have been provided)
if args.accounts != None:
    cpanel_backup_accounts = args.accounts
if args.workingdir != None:
    cpanel_backup_working_directory = args.workingdir
if args.retention != None:
    cpanel_backup_retention = args.retention
if args.email != None:
    cpanel_backup_email = args.email
if args.smtpserver != None:
    cpanel_backup_smtp_server = args.smtpserver
if args.smtpuser != None:
    cpanel_backup_smtp_user = args.smtpuser
if args.smtppassword != None:
    cpanel_backup_smtp_password = args.smtppassword
if args.destination != None:
    cpanel_backup_destination = args.destination
if args.excludeaccounts != None:
    cpanel_backup_exclude_accounts = args.excludeaccounts

# Variable Verification - Error if required variable is not provided.
# Now handled through the argparse
#if cpanel_backup_accounts == None:
#    sys.exit("ERROR: Required argument 'accounts' was not provided.") # Variable 'cpanel_backup_accounts'
#if cpanel_backup_destination == None:
#    sys.exit("ERROR: Required argument 'destination' was not provided.") # Variable 'cpanel_backup_destination'

# Retreive a Account information from WHM API
def cpanel_list_accounts():
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
def cpanel_accounts_filter():
    try:
        # Get cPanel Account Data
        cpanel_account_data = cpanel_list_accounts()
        
        # Verify cpanel_account_data variable - check if 'data' and 'acct' keys exist
        if not cpanel_account_data or "data" not in cpanel_account_data or "acct" not in cpanel_account_data["data"]:
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
            
            for account in cpanel_account_data["data"]["acct"]:
                for cpanel_user in cpanel_backup_accounts:
                    if account["user"] == cpanel_user:
                    #if account["user"].lower() == cpanel_user.lower():
                        cpanel_users_filtered.append(account)
        else:
            cpanel_users_filtered = cpanel_account_data
        return cpanel_users_filtered
    # Handle Exceptions
    except KeyError as e:
        print(f"Skipping account due to missing 'diskused' field: {e}")

# Add cPanel users disk usage together to estimate uncompressed backup size
def cpanel_account_size_estimate_mb():
    try:
        # Initalize cPanel Accounts Total Size Variable
        cpanel_uncompressed_size_mb = 0
        
        # Loop cPanel Accounts
        for account in cpanel_account_data["data"]["acct"]:
            try:
                # Make sure 'diskused' is valid
                if "diskused" not in account:
                    raise KeyError(f"Account {account} 'diskused' field is empty")
                    
                # Convert 'diskused' to Megabytes
                disk_used_mb = convert_to_mb(account["diskused"])
                
                # Add to cPanel total size
                cpanel_uncompressed_size_mb += disk_used_mb
                
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


# Get cPanel Account Data and Filter for selected Accounts
cpanel_account_data_filter = cpanel_accounts_filter()
print(cpanel_account_data_filter)

#print(type(cpanel_backup_accounts))
#print(cpanel_backup_accounts)
#print(type(cpanel_backup_accounts2))
#print(cpanel_backup_accounts2)


#user
#domain
#suspended = 0 (not suspended)
#diskused