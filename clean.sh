#!/bin/bash

# Check if config file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <config_file.json>"
    exit 1
fi

CONFIG_FILE="$1"

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Error: This script requires jq to parse JSON. Please install it first."
    echo "On Debian/Ubuntu: sudo apt-get install jq"
    echo "On macOS with Homebrew: brew install jq"
    exit 1
fi

# Extract server names and commands from the config file
echo "Reading config file: $CONFIG_FILE"
server_count=$(jq '.mcpServers | length' "$CONFIG_FILE")

if [ "$server_count" -eq 0 ]; then
    echo "No servers found in config file."
    exit 0
fi

# Process each server in the config
for server_name in $(jq -r '.mcpServers | keys[]' "$CONFIG_FILE"); do
    command_name=$(jq -r ".mcpServers.\"$server_name\".command" "$CONFIG_FILE")
    
    echo "Looking for processes matching server: $server_name (command: $command_name)"
    
    # Get process IDs matching the command name
    matching_pids=$(ps aux | grep "$server_name" | grep -v "grep" | awk '{print $2}')
    
    if [ -z "$matching_pids" ]; then
        echo "No processes found for $server_name"
    else
        # Kill each matching process
        for pid in $matching_pids; do
            echo "Killing process $pid (matched $server_name)"
            kill -9 "$pid"
            if [ $? -eq 0 ]; then
                echo "Successfully killed process $pid"
            else
                echo "Failed to kill process $pid"
            fi
        done
    fi
done

echo "Process check and cleanup completed."
