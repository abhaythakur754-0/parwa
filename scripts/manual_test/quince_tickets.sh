#!/bin/bash
# Creates 10 complicated Quince-style tickets via the UI
# Each ticket: customer name + email + subject + body + category + priority + channel

create_ticket() {
  local idx=$1
  local name=$2
  local email=$3
  local subject=$4
  local body=$5
  local category=$6
  local priority=$7
  local channel=$8

  echo ">>> Creating ticket $idx: $subject"
  # Open the modal
  agent-browser open https://parwa.buzz/dashboard/tickets
  agent-browser wait 4000
  agent-browser snapshot -i 2>&1 | tail -5
  # Click Create Ticket
  agent-browser find role button click --name "Create Ticket" 2>&1 | tail -2
  agent-browser wait 2000
  agent-browser snapshot -i 2>&1 | tail -5
}
