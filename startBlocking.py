import time
import subprocess
from webBlocker import DNSHandler, DNSSetupError, get_active_interface, run_dns_server
from appBlocker import *
import sys
import json
from parseAppListFile import clearSessionState, writeSessionState, readSessionState

def startBlocking(timeInSeconds, blockingDict):
    if len(blockingDict["Apps"]) == 0:
        print("No apps to block.")
    else:
        for app in blockingDict["Apps"]:
            #print(f"Blocking {app}...")
            if blockingDict["Apps"][app] == "extensionBlock":
                blockExtension(app, app.split("*")[0])
            elif blockingDict["Apps"][app] == "blackList":
                blacklistApps(app, blockingDict)
            elif blockingDict["Apps"][app] == "computerLock":
                lockComputer()
            else:
                lockapp(app)

    endTime = time.time() + timeInSeconds if timeInSeconds else None
    writeSessionState({
        "active": True,
        "start_time": time.time(),
        "end_time": endTime,
        "duration_seconds": timeInSeconds,
        "blocking_dict": json.dumps(blockingDict),
    })

    try:
        if len(blockingDict["Websites"]) == 0:
            print("No websites to block.")
            if endTime:
                while time.time() < endTime:
                    try:
                        if not readSessionState().get('active'):
                            break
                    except:
                        break
                    time.sleep(min(1, max(0, endTime - time.time())))
        else:
            try:
                websites = list(blockingDict["Websites"])
            except KeyError:
                websites = []

            if not websites:
                print("No websites to block.")
                if endTime:
                    while time.time() < endTime:
                        try:
                            if not readSessionState().get('active'):
                                break
                        except:
                            break
                        time.sleep(min(1, max(0, endTime - time.time())))
            else:
                iface = get_active_interface()
                if not iface:
                    print("Could not find an active network interface. Skipping website blocking.")
                    if endTime:
                        while time.time() < endTime:
                            try:
                                if not readSessionState().get('active'):
                                    break
                            except:
                                break
                            time.sleep(min(1, max(0, endTime - time.time())))
                else:
                    try:
                        DNSHandler.block_list = websites
                        duration = None if endTime is None else max(0, endTime - time.time())
                        run_dns_server(websites, duration=duration)
                    except DNSSetupError as error:
                        print(f"Website blocking is not available on this system: {error}")
                    except subprocess.CalledProcessError as error:
                        print(f"Website blocking could not start due to DNS configuration failure: {error}")
                    except OSError as error:
                        print(f"Website blocking could not start because UDP port 53 is already in use: {error}")
                    except Exception as error:
                        print(f"Website blocking failed: {error}")
    finally:
        try:
            if len(blockingDict["Apps"]) == 0:
                print("No apps to block.")
            else:
                for app in blockingDict["Apps"]:
                    #print(f"Blocking {app}...")
                    if blockingDict["Apps"][app] == "extensionBlock":
                        unlockExtension(app, app.split("*")[0])
                    elif blockingDict["Apps"][app] == "blackList":
                        unlockBlacklistApps(app, blockingDict)
                    elif blockingDict["Apps"][app] == "computerLock":
                        unlockComputer()
                    else:
                        unlockapp(app)
        finally:
            clearSessionState()

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        startBlocking(int(sys.argv[1]), json.loads(sys.argv[2]))
