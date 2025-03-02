#!/usr/bin/env python3

"""
This file contains functions required for main.py to function.

Author: Perrynaise
Date: 2025-02-16 (Feb 16th 2025)
"""

import sys
import os
import subprocess
import argparse
import json
import shutil

# Retreive a Account information from WHM API
def CpanelListAllAccounts():
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
def ConvertToMB(value):
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
def CpanelAccountsFilter(cpanel_accounts_list, cpanel_backup_accounts):
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
def CpanelAccountSizeEstimateMB(filtered_cpanel_accounts):
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
                disk_used_mb = ConvertToMB(account["diskused"])

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

def GetFreeSpaceLocalDisk(directory_path):
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