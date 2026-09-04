import os
import sys
from appBlocker import *
from parseAppListFile import turnToReadableDictonary, clearSessionState, scanForAppListFile, getAppListPath
from webBlocker import reset_dns, get_active_interface, DNSSetupError

def processListFile(filePath):
    """
    Process a text file by applying cleanup/unlock operations for all lists
    (equivalent to what happens at the end of startBlocking.py)
    
    Args:
        filePath: Path to a .txt list file
    """
    if not os.path.isfile(filePath):
        print(f"Error: {filePath} is not a valid file")
        return
    
    #print(f"Processing: {filePath}\n")
    
    try:
        # Get all namespaces in the file
        namespaces = scanForAppListFile(filePath)
        
        if not namespaces:
            print("No namespaces found in file")
            return
        
        totalAppsUnlocked = 0
        iface = None
        
        # Try to get active interface for DNS reset
        try:
            iface = get_active_interface()
            if iface:
                print(f"Active interface found: {iface}\n")
            else:
                print("Could not find an active network interface. Website unblocking will be skipped.\n")
        except Exception as e:
            print(f"Warning: Could not get active interface: {e}\n")
        
        # Process each namespace
        for namespace in namespaces:
            #print(f"Processing namespace: {namespace}")
            
            try:
                blockingDict = turnToReadableDictonary(filePath, namespace)
                
                if not blockingDict:
                    print(f"  Could not parse namespace {namespace}")
                    continue
                
                # Unlock apps
                if "Apps" in blockingDict and blockingDict["Apps"]:
                    for app in blockingDict["Apps"]:
                        appType = blockingDict["Apps"][app]
                        
                        try:
                            if appType == "extensionBlock":
                                unlockExtension(app, app.split("*")[0])
                                #print(f"  Unlocked extension: {app}")
                            elif appType == "blackList":
                                unlockBlacklistApps(app, blockingDict)
                                #print(f"  Unlocked blacklisted app: {app}")
                            elif blockingDict["Apps"][app] == "computerLock":
                                unlockComputer()
                                #print(f"  Unlocked computer lock: {app}")
                            else:  # normal lock
                                unlockapp(app)
                                #print(f"  Unlocked app: {app}")
                            
                            totalAppsUnlocked += 1
                        except Exception as e:
                            print(f"  Error unlocking {app}: {e}")
                else:
                    print(f"  No apps to unlock")
                
                # Unblock websites
                if "Websites" in blockingDict and blockingDict["Websites"]:
                    print(f"  Websites to unblock: {len(blockingDict['Websites'])}")
                    for website in blockingDict["Websites"]:
                        print(f"    - {website}")
                else:
                    print(f"  No websites to unblock")
            
            except Exception as e:
                print(f"  Error processing namespace {namespace}: {e}")
        
        # Reset DNS to restore website access
        if iface:
            try:
                print(f"\nResetting DNS on interface {iface}...")
                reset_dns(iface)
                print("DNS reset successfully")
            except DNSSetupError as e:
                print(f"Error resetting DNS: {e}")
            except Exception as e:
                print(f"Error resetting DNS: {e}")
        
        print(f"\n{'='*50}")
        print(f"Total apps unlocked: {totalAppsUnlocked}")
    
    except Exception as e:
        print(f"Error processing file: {e}")
    finally:
        # Clear session state at the end
        clearSessionState()
        print("Session state cleared")

if __name__ == "__main__":
    '''
    if len(sys.argv) < 2:
        processListFile(getAppListPath())
    
    filePath = sys.argv[1]'''
    filePath = "C:\\Users\\rossg\\Downloads\\overwolf.txt"
    processListFile(filePath)
    clearSessionState()