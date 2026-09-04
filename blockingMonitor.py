"""
Background monitoring service for FocusLock blocking.
Runs continuously and ensures blocking stays active if a session is ongoing.
Can be scheduled to run at system startup via Windows Task Scheduler.
"""

import time
import json
import sys
import os
import platform
import subprocess
from parseAppListFile import readSessionState, writeSessionState, getSessionStatePath, getAppListPath, getDataPath
from focusLock import buildBlockingCommand

def getBlockingProcessInfo():
    """Check if a blocking process is currently running (basic check)."""
    # On Windows, we could use psutil, but for simplicity we'll rely on 
    # the fact that if blocking crashed, the process won't exist
    # This is a basic implementation - could be enhanced with psutil
    return True  # Assume it's running; this would need proper process monitoring

def restartBlockingProcess(sessionState):
    """Restart the blocking process if it's not running."""
    try:
        blockingDict = json.loads(sessionState.get("blocking_dict", "{}"))
        timeInSeconds = sessionState.get("duration_seconds", 0)
        
        if timeInSeconds and blockingDict:
            payload = json.dumps(blockingDict)
            command = buildBlockingCommand(timeInSeconds, payload)
            
            if platform.system() == "Windows":
                subprocess.Popen(
                    command,
                    close_fds=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                )
            else:
                subprocess.Popen(command, close_fds=True)
            
            print(f"[BlockingMonitor] Restarted blocking process at {time.ctime()}")
            return True
    except Exception as e:
        print(f"[BlockingMonitor] Error restarting blocking: {e}")
    
    return False

def monitorBlocking(checkIntervalSeconds=5):
    """
    Continuously monitor the blocking session.
    
    Args:
        checkIntervalSeconds: How often to check session state (default 5 seconds)
    """
    print(f"[BlockingMonitor] Started monitoring at {time.ctime()}")
    
    while True:
        try:
            sessionState = readSessionState()
            
            if not sessionState or not sessionState.get("active"):
                # No active session, check again in a bit
                time.sleep(checkIntervalSeconds)
                continue
            
            # Check if session has expired
            endTime = sessionState.get("end_time")
            if endTime and endTime <= time.time():
                # Session expired, mark as inactive
                sessionState["active"] = False
                writeSessionState(sessionState)
                print(f"[BlockingMonitor] Session expired at {time.ctime()}")
                time.sleep(checkIntervalSeconds)
                continue
            
            # Session is active - attempt to restart blocking if needed
            # In production, you'd check if the actual blocking process is running
            # For now, we restart it if the session state exists
            restartBlockingProcess(sessionState)
            
            # Check again after interval
            time.sleep(checkIntervalSeconds)
            
        except Exception as e:
            print(f"[BlockingMonitor] Error in monitoring loop: {e}")
            time.sleep(checkIntervalSeconds)

if __name__ == "__main__":
    # Run the monitoring service
    # This will be called by Windows Task Scheduler at startup
    try:
        monitorBlocking(checkIntervalSeconds=10)
    except KeyboardInterrupt:
        print("[BlockingMonitor] Monitoring stopped")
        sys.exit(0)
