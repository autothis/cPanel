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

    Example Script Execution:
        "cpanel-backup.py --accounts 'all' --workingdir '/tmp' --retention '7' --email 'cpaneladmin@example.com' --smtpserver 'smtp.example.com' --smtpuser 'smtpuser' --smtppassword 'smtpP@ssw0rd' --destination '/backupdrive'"
            or
        "cpanel-backup.py --accounts 'all' \
            --workingdir '/tmp' \
            --retention '7' \
            --email 'cpaneladmin@example.com' \
            --smtpserver 'smtp.example.com' \
            --smtpuser 'smtpuser' \
            --smtppassword 'smtpP@ssw0rd' \
            --destination '/backupdrive' \
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

# Manually Defined Variables - These will be individually overriden if matching argument is passed from commandline.
cpanel_backup_accounts = ""             # This is a list of one or more cPanel accounts to be backed up, or if 'all' is specified all cPanel accounts.
cpanel_backup_working_directory = ""    # This is where the script will store the tar.gz as it is created, and will be kept until a verified transfer to the backup location is completed.  Defaults to /home if not specified.
cpanel_backup_retention = ""            # This is the number of backups to be kept - it is NOT days or weeks.
cpanel_backup_email = ""                # Email address to receive notifications.
cpanel_backup_smtp_server = ""          # SMTP server responsible for sending notifications.
cpanel_backup_smtp_user = ""            # SMTP server authentication username
cpanel_backup_smtp_password = ""        # SMTP server authentication password
cpanel_backup_destination = ""          # Destination for cPanel backup files

# Variables to keep track of - List of variables used in this script, and what they are used for.
cpanel_backup_running_size = ""     # This is the running total for backup file sizes, to be provided in email notification to help with capacity planning.

# Import Arguments
parser=argparse.ArgumentParser()
parser.add_argument("--accounts", help="cPanel Accounts to be backedup. Comma separated list containing one or more cPanel accounts.  Can specify 'all' to backup all accounts.")
parser.add_argument("--workingdir", help="This is where the script will store the tar.gz as it is created, and will be kept until a verified transfer to the backup location is compelted.  Defaults to /home if not specified.")
parser.add_argument("--retention", help="This is the number of backups to be kept - it is NOT days or weeks")
parser.add_argument("--email", help="Email address to receive notifications")
parser.add_argument("--smtpserver", help="SMTP server responsible for sending notifications")
parser.add_argument("--smtpuser", help="SMTP server authentication username")
parser.add_argument("--smtppassword", help="SMTP server authentication password")
parser.add_argument("--destination", help="Destination for cPanel backup files")
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

# Variable Verification - Error if required variable is not provided.
if cpanel_backup_accounts == None:
    sys.exit("ERROR: Required argument 'accounts' was not provided.") # Variable 'cpanel_backup_accounts'
if cpanel_backup_destination == None:
    sys.exit("ERROR: Required argument 'destination' was not provided.") # Variable 'cpanel_backup_destination'

def cpanel_list_accounts():
    try:
        result = subprocess.run(
            args = ["/usr/local/cpanel/bin/whmapi1", "--output=json", "listacctss"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        response = json.loads(result.stdout)
        if response["metadata"]["result"] ==0:
            raise ValueError("whmapi1 query failed", response["metadata"]["reason"])
            # response["metadata"]["result"] alue of 0 is a failure, 1 is a success
        return response    
    except Exception as e:
        # Handle unexpected exceptions
        print(f"An unexpected error occurred: {e}")
        return None