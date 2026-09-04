import tkinter as tk 
import tkinter.ttk as ttk
from tkinter import scrolledtext
import tkinter.font as tkFont
import customtkinter as ctk
import time
from extensionFinder import findFileType
import getpass
import sys
import platform
import ctypes
import os
import json
import subprocess
from startBlocking import startBlocking
from parseAppListFile import turnToReadableDictonary, scanForAppListFile, saveList, getDataPath, getAppListPath, readSessionState, clearSessionState, deleteList, writeSessionState

def attemptResumeBlockingSession():
    """
    On app startup, check if there was an active blocking session.
    If so, attempt to restart the blocking process.
    This handles the case where the device was powered off during blocking.
    """
    sessionState = readSessionState()
    if not sessionState or not sessionState.get("active"):
        return  # No active session to resume
    
    # Check if session has expired
    endTime = sessionState.get("end_time")
    if endTime and endTime <= time.time():
        clearSessionState()
        return  # Session expired, clear it
    
    # Session is still valid, restart blocking
    try:
        blockingDict = json.loads(sessionState.get("blocking_dict", "{}"))
        timeInSeconds = sessionState.get("duration_seconds", 0)
        
        if timeInSeconds and blockingDict:
            payload = json.dumps(blockingDict)
            command = buildBlockingCommand(timeInSeconds, payload)
            
            if platform.system() == "Windows":
                if isElevated():
                    subprocess.Popen(
                        command,
                        close_fds=True,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                    )
                else:
                    targetPath = command[0]
                    arguments = subprocess.list2cmdline(command[1:])
                    result = ctypes.windll.shell32.ShellExecuteW(
                        None,
                        "runas",
                        targetPath,
                        arguments,
                        None,
                        0
                    )
            else:
                subprocess.Popen(command, close_fds=True)
    except Exception as e:
        print(f"Failed to resume blocking session: {e}")

def setupWindowsTaskScheduler():
    """
    Set up Windows Task Scheduler to run the blocking monitor at system startup.
    This ensures blocking is automatically restarted even if the app isn't open.
    """
    if platform.system() != "Windows":
        return
    
    try:
        monitorScriptPath = os.path.abspath(os.path.join(os.path.dirname(__file__), "blockingMonitor.py"))
        if not os.path.exists(monitorScriptPath):
            return  # Script doesn't exist, skip setup
        
        taskName = "FocusLockBlockingMonitor"
        pythonExe = sys.executable
        
        # Create Task Scheduler command
        powershellCommand = (
            f"$TaskName = '{taskName}'; "
            f"$TaskPath = '\\'; "
            f"if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {{ "
            f"Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false; "
            f"}}; "
            f"$Action = New-ScheduledTaskAction -Execute '{escapePowerShellString(pythonExe)}' "
            f"-Argument '\"{escapePowerShellString(monitorScriptPath)}\"'; "
            f"$Trigger = New-ScheduledTaskTrigger -AtStartup; "
            f"$Principal = New-ScheduledTaskPrincipal -UserId (whoami) -LogonType Interactive; "
            f"$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RunOnlyIfNetworkAvailable:$false; "
            f"Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null"
        )
        
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", powershellCommand],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"Failed to setup Task Scheduler: {e}")

def center(win):
    # Source - https://stackoverflow.com/a/10018670
    # Posted by Honest Abe, modified by the community. See post 'Timeline' for change history
    # Retrieved 2026-03-16, License - CC BY-SA 4.0
    """
    centers a tkinter window
    :param win: the main window or Toplevel window to center
    """
    win.update_idletasks()
    width = win.winfo_width()
    frmWidth = win.winfo_rootx() - win.winfo_x()
    winWidth = width + 2 * frmWidth
    height = win.winfo_height()
    titlebarHeight = win.winfo_rooty() - win.winfo_y()
    winHeight = height + titlebarHeight + frmWidth
    x = win.winfo_screenwidth() // 2 - winWidth // 2
    y = win.winfo_screenheight() // 2 - winHeight // 2
    win.geometry('{}x{}+{}+{}'.format(width, height, x, y))
    win.deiconify()

def getDesktopPath():
    if platform.system() != "Windows":
        return None

    desktopBuffer = ctypes.create_unicode_buffer(260)
    CSIDL_DESKTOPDIRECTORY = 0x0010
    result = ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOPDIRECTORY, None, 0, desktopBuffer)
    if result == 0 and os.path.isdir(desktopBuffer.value):
        return desktopBuffer.value

    return None

def escapePowerShellString(value):
    return value.replace("'", "''")

def isBlockingMode():
    return len(sys.argv) >= 2 and sys.argv[1] == "--start-blocking"

def isElevated():
    if platform.system() != "Windows":
        return True

    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False

def runBlockingMode():
    if len(sys.argv) < 4:
        return
    startBlocking(int(sys.argv[2]), json.loads(sys.argv[3]))

def getBlockingExecutable():
    if getattr(sys, "frozen", False):
        executableDir = os.path.dirname(sys.executable)
        helperExe = os.path.join(executableDir, "startBlocking.exe")
        if os.path.exists(helperExe):
            return helperExe
        return sys.executable

    helperScript = os.path.join(os.path.dirname(os.path.abspath(__file__)), "startBlocking.py")
    if os.path.exists(helperScript):
        return helperScript
    return os.path.abspath(__file__)

def buildBlockingCommand(timeInSeconds, payload):
    helperTarget = getBlockingExecutable()

    if getattr(sys, "frozen", False):
        if os.path.basename(helperTarget).lower() == "startblocking.exe":
            return [helperTarget, str(timeInSeconds), payload]
        return [helperTarget, "--start-blocking", str(timeInSeconds), payload]

    if os.path.basename(helperTarget).lower() == "startblocking.py":
        return [sys.executable, helperTarget, str(timeInSeconds), payload]
    return [sys.executable, helperTarget, "--start-blocking", str(timeInSeconds), payload]

def ensureDesktopShortcut():
    if platform.system() != "Windows":
        return

    desktopPath = getDesktopPath()
    if not desktopPath:
        return

    shortcutPath = os.path.join(desktopPath, "FocusLock.lnk")
    if os.path.exists(shortcutPath):
        return

    if getattr(sys, "frozen", False):
        targetPath = sys.executable
        arguments = ""
        workingDirectory = os.path.dirname(sys.executable)
    else:
        targetPath = sys.executable
        arguments = f'"{os.path.abspath(__file__)}"'
        workingDirectory = os.path.dirname(os.path.abspath(__file__))

    iconPath = getDataPath("logo.ico")
    powershellCommand = (
        "$WshShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{escapePowerShellString(shortcutPath)}'); "
        f"$Shortcut.TargetPath = '{escapePowerShellString(targetPath)}'; "
        f"$Shortcut.Arguments = '{escapePowerShellString(arguments)}'; "
        f"$Shortcut.WorkingDirectory = '{escapePowerShellString(workingDirectory)}'; "
        f"$Shortcut.IconLocation = '{escapePowerShellString(iconPath)}'; "
        "$Shortcut.Save()"
    )

    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", powershellCommand],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except (subprocess.SubprocessError, OSError):
        pass

#webBlockerSetup()

class ScrollableFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.canvas = tk.Canvas(self, bg='#111937', highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)

        self.scrollableFrame = tk.Frame(self.canvas, bg='#111937')

        # Update scroll region + show/hide scrollbar
        self.scrollableFrame.bind("<Configure>", self._on_frame_configure)

        self.window = self.canvas.create_window(
            (0, 0),
            window=self.scrollableFrame,
            anchor="nw"
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Mouse wheel bindings
        self._bind_mousewheel()
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_frame_configure(self, event=None):
        bbox = self.canvas.bbox("all")
        if bbox is None:
            return

        self.canvas.configure(scrollregion=bbox)

        if bbox[3] <= self.canvas.winfo_height():
            self.scrollbar.pack_forget()
        else:
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(side="right", fill="y")
    
    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.window, width=event.width)

    # ---------------------------
    # Mouse wheel support
    # ---------------------------
    def _bind_mousewheel(self):
        # Windows / MacOS
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Linux (scroll up/down)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    
    def _on_mousewheel(self, event):
        if event.delta == 0:
            return

        # Normalize scroll direction
        delta = -event.delta / 120  # Windows standard

        bbox = self.canvas.bbox("all")
        if not bbox:
            return

        contentHeight = bbox[3]
        visibleHeight = self.canvas.winfo_height()

        if contentHeight <= visibleHeight:
            return

        # Convert pixels → fraction
        pixelsPerScroll = 30  # tweak for smoothness
        move = (delta * pixelsPerScroll) / contentHeight

        current = self.canvas.yview()[0]
        self.canvas.yview_moveto(current + move)

    def _on_mousewheel_linux(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "pixels")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "pixels")

class tkinterApp(tk.Tk):
    # __init__ function for class tkinterApp 
    def __init__(self, *args, **kwargs): 
        
        # __init__ function for class Tk
        tk.Tk.__init__(self, *args, **kwargs)
        
        
        if platform.system() == "Windows":
            myAppId = 'FocusLockInc.FocusLock.mainApp.Beta' # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myAppId)
            self.iconbitmap(getDataPath("logo.ico"))
            ensureDesktopShortcut()
            setupWindowsTaskScheduler()
        else:
            self.iconphoto(False, tk.PhotoImage(file=getDataPath("logo.png")))
        
        self.title("FocusLock")
        width = self.winfo_screenwidth()
        height = self.winfo_screenheight()
        width = int(width * 0.5)
        height = int(height * 0.5)
        #print("width=",width) 768
        #print("height=",height) 432
        self.geometry(f"{width}x{height}")
        center(self)
        self.configure(bg='#111937')
        self.baseWidth = width
        self.baseHeight = height
        self.resizeAfterId = None
        self.unscaledWidgets = {}
        
        # Fonts:
        global schoolReallyBigFont
        schoolReallyBigFont = tkFont.Font(family="Century Schoolbook", size=24, weight=tkFont.NORMAL, name="schoolReallyBigFont")
        global schoolBigFont
        schoolBigFont = tkFont.Font(family="Century Schoolbook", size=20, weight=tkFont.NORMAL, name="schoolBigFont")
        global schoolMediumFont
        schoolMediumFont = tkFont.Font(family="Century Schoolbook", size=16, weight=tkFont.NORMAL, name="schoolMediumFont")
        global schoolSmallFont
        schoolSmallFont = tkFont.Font(family="Century Schoolbook", size=12, weight=tkFont.NORMAL, name="schoolSmallFont")
        global schoolCTKFont
        schoolCTKFont = ctk.CTkFont(family="Century Schoolbook", size=16, weight="normal")

        frame = tk.Frame(self)
        frame.pack(padx=10, pady=10, side="top", fill="x")

        frame.configure(bg='#0a7543')

        homeButton = tk.Label(frame,
                            text="Home",
                            activebackground="#0a7543",
                            activeforeground="#111937",
                            anchor="nw",
                            bd=3,
                            bg="#0a7543",
                            cursor="hand2",
                            disabledforeground="#0a7543",
                            fg="#111937",
                            font=schoolReallyBigFont,
                            justify="center")

        homeButton.pack(padx=10, pady=5, side="left")
        homeButton.bind("<Button-1>", lambda e: self.show_frame(Home))

        appAdder = tk.Label(frame,
                            text="Add Sites/Apps",
                            activebackground="#0a7543",
                            activeforeground="#111937",
                            anchor="n",
                            bd=3,
                            bg="#0a7543",
                            cursor="hand2",
                            disabledforeground="#0a7543",
                            fg="#111937",
                            font=schoolReallyBigFont,
                            justify="center")

        appAdder.pack(padx=10, pady=5, side="left", expand=True)
        appAdder.bind("<Button-1>", lambda e: self.show_frame(AddApps))

        exitButton = tk.Label(frame,
                            text="Exit",
                            activebackground="#0a7543",
                            activeforeground="#111937",
                            anchor="ne",
                            bd=3,
                            bg="#0a7543",
                            cursor="hand2",
                            disabledforeground="#0a7543",
                            fg="#111937",
                            font=schoolReallyBigFont,
                            justify="center")

        exitButton.pack(padx=10, pady=5, side="right")
        exitButton.bind("<Button-1>", lambda event: self.destroy())

        # creating a container
        container = tk.Frame(self)
        container.pack(side = "top", fill = "both", expand = True) 
        container.configure(bg='#111937')
 
        container.grid_rowconfigure(0, weight = 1)
        container.grid_columnconfigure(0, weight = 1)
 
        # initializing frames to an empty array
        self.frames = {}  
 
        # iterating through a tuple consisting
        # of the different page layouts
        for F in (Home, AddApps):
 
            frame = F(container, self, self.refreshAllDropdowns)
 
            # initializing frame of that object from
            # startpage, page1, page2 respectively with 
            # for loop
            self.frames[F] = frame 
 
            frame.grid(row = 0, column = 0, sticky ="nsew")
 
        self.show_frame(Home)
        self.bind("<Configure>", self.scheduleResponsiveResize)
        self.scheduleResponsiveResize()

    def scheduleResponsiveResize(self, event=None):
        if self.resizeAfterId is not None:
            self.after_cancel(self.resizeAfterId)
        self.resizeAfterId = self.after(50, self.applyResponsiveResize)

    def applyResponsiveResize(self):
        self.resizeAfterId = None
        currentWidth = max(self.winfo_width(), 1)
        currentHeight = max(self.winfo_height(), 1)
        scale = min(currentWidth / self.baseWidth, currentHeight / self.baseHeight)
        scale = max(0.75, min(scale, 1.5))

        fontSizes = [
            (schoolReallyBigFont, 24),
            (schoolBigFont, 20),
            (schoolMediumFont, 16),
            (schoolSmallFont, 12),
        ]
        for font, baseSize in fontSizes:
            font.configure(size=max(8, round(baseSize * scale)))
        schoolCTKFont.configure(size=max(8, round(16 * scale)))

        for widget, fonts in self.unscaledWidgets.items():
            if widget.winfo_exists():
                widget.configure(font=fonts[1])

        for frame in self.frames.values():
            if hasattr(frame, "handleResponsiveResize"):
                frame.handleResponsiveResize(scale, currentWidth)

    def setWidgetScaling(self, widget, enabled=True):
        if enabled:
            fonts = self.unscaledWidgets.pop(widget, None)
            if fonts and widget.winfo_exists():
                widget.configure(font=fonts[0])
            return

        currentFont = widget.cget("font")
        if currentFont:
            self.unscaledWidgets[widget] = (
                currentFont,
                tkFont.Font(font=currentFont),
            )
 
    def refreshAllDropdowns(self):
        """
        Refresh the list menus in both Home and AddApps frames
        when lists are added or deleted.
        """
        homeFrame = self.frames.get(Home)
        if homeFrame and hasattr(homeFrame, 'refreshListMenu'):
            homeFrame.refreshListMenu()
        
        addAppsFrame = self.frames.get(AddApps)
        if addAppsFrame and hasattr(addAppsFrame, 'refreshListMenu'):
            addAppsFrame.refreshListMenu()
    
    # to display the current frame passed as
    # parameter
    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()

class Home(tk.Frame):
    def __init__(self, parent, controller, refreshCallback=None): 
        tk.Frame.__init__(self, parent)
        self.configure(bg='#111937')
        self.countdownAfterId = None
        self.refreshCallback = refreshCallback
        self.listMenu = None
        self.sessionControlsHidden = False
        self.sessionStartPending = False
        self.sessionWasActive = False
        self.breakStartPending = False
        self.breakWasActive = False
        self.breakEndTime = None
        self.breakPromptVisible = False

        self.pinnedTimer = tk.Toplevel(self)
        self.pinnedTimer.title("Pinned Timer")

        '''if platform.system() == "Windows":
            self.iconbitmap(getDataPath("logo.ico"))
            ensureDesktopShortcut()
            setupWindowsTaskScheduler()
        else:
            self.iconphoto(False, tk.PhotoImage(file=getDataPath("logo.png")))'''

        window_width = 300
        window_height = 50
        screen_width = self.pinnedTimer.winfo_screenwidth()
        screen_height = self.pinnedTimer.winfo_screenheight()

        x = screen_width - window_width - 50
        y = screen_height - window_height - 100  # Extra space for taskbar

        self.pinnedTimer.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.pinnedTimer.resizable(False, False)
        self.pinnedTimer.attributes("-topmost", True)

        self.pinnedTimer.configure(bg="#111937")

        self.pinnedTimerVariable = tk.StringVar(value="No active focus session")
        pinnedTimer = tk.Label(
                    self.pinnedTimer,
                    textvariable=self.pinnedTimerVariable,
                    font=schoolSmallFont,
                    bg="#111937",
                    fg="#DFF1DA",
                    justify="center",
                    cursor="fleur"
                )
        pinnedTimer.bind("<Button-1>", self.start_move)
        pinnedTimer.bind("<B1-Motion>", self.do_move)
        self.pinnedTimer.overrideredirect(True)
        pinnedTimer.pack(padx=10, pady=5, fill="both", expand=True)
        controller.setWidgetScaling(pinnedTimer, False)
        self.pinnedTimer.withdraw()

        scroll = ScrollableFrame(self)
        scroll.pack(fill="both", expand=True)

        container = scroll.scrollableFrame

        # label of frame Layout 2
        self.label = ttk.Label(
            container,
            text ="Home",
            font = schoolReallyBigFont,
            background="#111937",
            foreground="#0a7543",
            justify="center")

        self.countdownVar = tk.StringVar(value="No active focus session")
        self.countdownLabel = tk.Label(
            container,
            textvariable=self.countdownVar,
            font=schoolBigFont,
            bg="#111937",
            fg="#DFF1DA",
            justify="center"
        )

        self.timeFrame = tk.Frame(container, bg="#111937")

        hourLabel = tk.Label(self.timeFrame,
                            text="Hours",
                            font=schoolSmallFont,
                            bg="#111937",
                            fg="#0a7543",)
        hourLabel.grid(padx=0, pady=0, column=0, row=0)
        minuteLabel = tk.Label(self.timeFrame,
                            text="Minutes",
                            font=schoolSmallFont,
                            bg="#111937",
                            fg="#0a7543",)
        minuteLabel.grid(padx=0, pady=0, column=2, row=0)

        secondLabel = tk.Label(self.timeFrame,
                            text="Seconds",
                            font=schoolSmallFont,
                            bg="#111937",
                            fg="#0a7543",)
        secondLabel.grid(padx=0, pady=0, column=4, row=0)

        self.hours = tk.Spinbox(self.timeFrame,
                            from_=0,
                            to=float('inf'),
                            width=7,
                            relief="sunken",
                            repeatdelay=500,
                            repeatinterval=100,
                            font=schoolMediumFont,
                            bg="#DFF1DA",
                            fg="#172D11",
                            justify="center")
        self.hours.grid(padx=0, pady=0, column=0, row=1)

        minuteSeperator = tk.Label(self.timeFrame,
                            text=":",
                            font=schoolMediumFont,
                            bg="#DFF1DA",
                            fg="#172D11",)
        minuteSeperator.grid(padx=0, pady=0, column=1, row=1)

        self.minutes = tk.Spinbox(self.timeFrame,
                            from_=0,
                            to=59,
                            width=7,
                            relief="sunken",
                            repeatdelay=500,
                            repeatinterval=100,
                            font=schoolMediumFont,
                            bg="#DFF1DA",
                            fg="#172D11",
                            justify="center")
        self.minutes.grid(padx=0, pady=0, column=2, row=1)

        hourSeperator = tk.Label(self.timeFrame,
                            text=":",
                            font=schoolMediumFont,
                            bg="#DFF1DA",
                            fg="#172D11",)
        hourSeperator.grid(padx=0, pady=0, column=3, row=1)

        self.seconds = tk.Spinbox(self.timeFrame,
                            from_=0,
                            to=59,
                            width=7,
                            relief="sunken", 
                            repeatdelay=500,
                            repeatinterval=100,
                            font=schoolMediumFont,
                            bg="#DFF1DA",
                            fg="#172D11",
                            justify="center")
        self.seconds.grid(padx=0, pady=0, column=4, row=1)

        global toggleOverlay
        toggleOverlay = ctk.StringVar(value="off")

        # Create the modern switch widget
        self.overlaySwitch = ctk.CTkSwitch(
            container, 
            text="Toggle Overlay Timer", 
            font=schoolCTKFont,
            button_color="#DFF1DA",
            button_hover_color="#B9C8B5",
            progress_color="#0a7543",
            command=self.toggleOverlayTimer,
            variable=toggleOverlay, 
            onvalue="on", 
            offvalue="off"
        )


        def updateMenu(value):
            self.listMenu.config(text=f"Using: {value}")

        # ---- DROPDOWN ----
        self.listMenu = tk.Menubutton(
            container,
            text="Using: Default",
            bg="#DFF1DA",
            font=schoolBigFont,
            fg="#172D11",
            activebackground="#DFF1DA",
            cursor="hand2",
        )

        self.listMenu.menu = tk.Menu(self.listMenu, tearoff=0)
        self.listMenu["menu"] = self.listMenu.menu
        self._populateListMenu(updateMenu)

        self.startButton = tk.Label(container,
                            text="Start Focus Session",
                            font=schoolMediumFont,
                            bg="#0a7543",
                            fg="#111937",
                            cursor="hand2",)
        self.startButton.bind("<Button-1>", lambda event: self.handleStartStop())

        self.cancelBreak = tk.Label(container,
                            text="Cancel Break Session",
                            font=schoolMediumFont,
                            bg="#0a7543",
                            fg="#111937",
                            cursor="hand2",)
        self.cancelBreak.bind("<Button-1>", lambda event: self.handleCancelBreak())

        self.rePack()
        
        # Attempt to resume any interrupted blocking session
        attemptResumeBlockingSession()
        self.refreshCountdown()

    def handleResponsiveResize(self, scale, windowWidth):
        self.hours.configure(width=max(4, round(7 * scale)))
        self.minutes.configure(width=max(4, round(7 * scale)))
        self.seconds.configure(width=max(4, round(7 * scale)))

    def _populateListMenu(self, updateMenuCallback):
        """
        Populate the list menu dropdown with available lists.
        """
        self.listMenu.menu.delete(0, 'end')
        for i in scanForAppListFile(getAppListPath()):
            self.listMenu.menu.add_command(
                label=i,
                command=lambda v=i: updateMenuCallback(v),
                background="#DFF1DA",
                font=schoolSmallFont,
                foreground="#172D11",
            )
    
    def refreshListMenu(self):
        """
        Refresh the list menu dropdown when lists are added or deleted.
        """
        if self.listMenu:
            def updateMenu(value):
                self.listMenu.config(text=f"Using: {value}")
            self._populateListMenu(updateMenu)
    
    def formatRemainingTime(self, totalSeconds):
        totalSeconds = max(0, int(totalSeconds))
        hours, remainder = divmod(totalSeconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def getActiveSessionState(self):
        state = readSessionState()
        if not state or not state.get("active"):
            return None

        endTime = state.get("end_time")
        if endTime and endTime <= time.time():
            clearSessionState()
            return None

        return state

    def onBlockingSessionEnded(self):
        if not self.sessionControlsHidden:
            return

        self.sessionStartPending = False
        self.sessionWasActive = False

        self.showBreakUi()

        self.update_idletasks()

    def refreshBreakCountdown(self):
        self.countdownAfterId = None

        if not self.breakWasActive or self.breakEndTime is None:
            return

        self.breakStartPending = False
        remainingSeconds = self.breakEndTime - time.time()
        if remainingSeconds <= 0:
            self.breakWasActive = False
            self.breakStartPending = False
            self.breakEndTime = None
            self.countdownVar.set("Break complete")
            self.pinnedTimerVariable.set("Break complete")
            self.showSessionControls()
            self.startButton.config(text="Start Focus Session")
            return

        remainingTime = self.formatRemainingTime(remainingSeconds)
        self.countdownVar.set(f"Break Time Remaining: {remainingTime}")
        self.pinnedTimerVariable.set(f"Break Time Remaining: {remainingTime}")
        self.startButton.config(text="Stop Break Session")

        if self.winfo_exists():
            self.countdownAfterId = self.after(1000, self.refreshBreakCountdown)
    
    def refreshCountdown(self):
        self.countdownAfterId = None

        if self.breakPromptVisible and not self.breakWasActive and not self.breakStartPending:
            return

        if self.breakWasActive or self.breakStartPending:
            self.refreshBreakCountdown()
            return

        sessionState = self.getActiveSessionState()

        if not sessionState:

            # If we just started a session, give the blocking process
            # time to create/write the session state.
            if self.sessionStartPending:

                self.countdownVar.set("Starting focus session...")
                self.pinnedTimerVariable.set("Starting focus session...")
                self.startButton.config(text="Starting...")

            else:

                self.countdownVar.set("No active focus session")
                self.pinnedTimerVariable.set("No active focus session")
                self.startButton.config(text="Start Focus Session")

                # Only restore the controls if there actually was
                # an active session that has now ended.
                if self.sessionWasActive and self.sessionControlsHidden:
                    self.onBlockingSessionEnded()

                self.sessionWasActive = False

        else:
            # Session successfully started
            self.sessionWasActive = True
            self.sessionStartPending = False

            endTime = sessionState.get("end_time")

            if endTime:
                remainingTime = self.formatRemainingTime(
                    endTime - time.time()
                )

                self.countdownVar.set(
                    f"Time Remaining: {remainingTime}"
                )

                self.pinnedTimerVariable.set(
                    f"Time Remaining: {remainingTime}"
                )

            else:
                self.countdownVar.set("Focus session running")
                self.pinnedTimerVariable.set("Focus session running")

            self.startButton.config(text="Stop Focus Session")

            # Make sure controls stay hidden during an active session
            if not self.sessionControlsHidden:
                self.hideSessionControls()

        if self.winfo_exists():
            self.countdownAfterId = self.after(
                1000,
                self.refreshCountdown
            )

    def getTime(self):
        try:
            hours = int(self.hours.get())
            minutes = int(self.minutes.get())
            seconds = int(self.seconds.get())
            total_seconds = hours * 3600 + minutes * 60 + seconds
            #print(f"Total time in seconds: {total_seconds}")
            return total_seconds
        except ValueError:
            #print("Please enter valid integers for hours, minutes, and seconds.")
            return None

    def launchBlockingProcess(self, timeInSeconds, blockingDict):
        if timeInSeconds is None or timeInSeconds <= 0:
            return False

        if self.getActiveSessionState():
            return False

        payload = json.dumps(blockingDict)
        command = buildBlockingCommand(timeInSeconds, payload)

        if platform.system() == "Windows":

            if isElevated():

                subprocess.Popen(
                    command,
                    close_fds=True,
                    creationflags=(
                        subprocess.CREATE_NEW_PROCESS_GROUP |
                        subprocess.DETACHED_PROCESS
                    )
                )

                return True

            else:

                targetPath = command[0]
                arguments = subprocess.list2cmdline(command[1:])

                result = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    targetPath,
                    arguments,
                    None,
                    0
                )

                if result <= 32:
                    return False

                return True

        else:

            command = [
                sys.executable,
                os.path.abspath(__file__),
                "--start-blocking",
                str(timeInSeconds),
                payload
            ]

            subprocess.Popen(
                command,
                close_fds=True
            )

            return True

    def handleStartStop(self):
        # ==========================
        # STOP AN ACTIVE SESSION
        # ==========================
        if self.getActiveSessionState():
            clearSessionState()

            self.sessionStartPending = False
            self.sessionWasActive = False

            self.onBlockingSessionEnded()

            self.countdownVar.set("No active focus session")
            self.pinnedTimerVariable.set("No active focus session")
            self.startButton.config(text="Start Focus Session")

            return

        timeInSeconds = self.getTime()

        # Don't start if the entered time is invalid
        if timeInSeconds is None or timeInSeconds <= 0:
            return

        # Get the selected blocking list
        blockingDict = turnToReadableDictonary(
            getAppListPath(),
            self.listMenu.cget("text").split("Using: ")[1]
        )

        # Try to launch the blocking process
        success = self.launchBlockingProcess(
            timeInSeconds,
            blockingDict
        )

        if success:
            # Tell refreshCountdown() that we're waiting for the session state to appear.
            self.sessionStartPending = True

            # Remember that a session has been started
            self.sessionWasActive = True

            # Hide unnecessary UI
            self.hideSessionControls()

        else:
            self.sessionStartPending = False
            self.sessionWasActive = False

            # Make sure the normal UI is visible
            self.showBreakUi()

    def toggleOverlayTimer(self):
        if toggleOverlay.get() == "on":
            self.pinnedTimer.deiconify()
        else:
            self.pinnedTimer.withdraw()

    def start_move(self, event):
        self.pinnedTimer.x = event.x
        self.pinnedTimer.y = event.y

    def do_move(self, event):
        deltax = event.x - self.pinnedTimer.x
        deltay = event.y - self.pinnedTimer.y
        x = self.pinnedTimer.winfo_x() + deltax
        y = self.pinnedTimer.winfo_y() + deltay
        self.pinnedTimer.geometry(f"+{x}+{y}")

    def hideSessionControls(self):
        if self.sessionControlsHidden:
            return

        # Hide setup/session configuration UI
        self.label.pack_forget()
        self.timeFrame.pack_forget()
        self.listMenu.pack_forget()

        # Keep countdownLabel and startButton visible

        self.sessionControlsHidden = True
        self.update_idletasks()

    def handleCancelBreak(self):
        if self.countdownAfterId is not None:
            self.after_cancel(self.countdownAfterId)
            self.countdownAfterId = None

        self.breakStartPending = False
        self.breakWasActive = False
        self.breakEndTime = None
        self.breakPromptVisible = False
        self.showSessionControls()
        self.countdownVar.set("No active focus session")
        self.pinnedTimerVariable.set("No active focus session")
        self.startButton.config(text="Start Focus Session")

    def handleBreakStop(self):
        self.handleCancelBreak()

    def startBreakSession(self):
        breakTimeInSeconds = self.getTime()
        if breakTimeInSeconds is None or breakTimeInSeconds <= 0:
            self.handleCancelBreak()
            return

        if self.getActiveSessionState():
            return

        self.breakStartPending = True
        self.breakWasActive = True
        self.breakEndTime = time.time() + breakTimeInSeconds
        self.startButton.bind("<Button-1>", lambda event: self.handleBreakStop())
        self.hideSessionControls()
        if self.countdownAfterId is not None:
            self.after_cancel(self.countdownAfterId)
            self.countdownAfterId = None
        self.refreshBreakCountdown()

    def showBreakUi(self):
        # Remove everything first
        self.label.pack_forget()
        self.countdownLabel.pack_forget()
        self.timeFrame.pack_forget()
        self.overlaySwitch.pack_forget()
        self.listMenu.pack_forget()
        self.startButton.pack_forget()

        # Configure buttons
        self.startButton.bind("<Button-1>", lambda event: self.startBreakSession())

        # Add break ui
        self.countdownVar.set("You did it! Start a break?")
        self.startButton.config(text="Start Break Session")
        self.label.pack(padx=10, pady=10)
        self.countdownLabel.pack(padx=10, pady=5)
        self.timeFrame.pack(padx=0, pady=10)
        self.overlaySwitch.pack(pady=5)
        self.startButton.pack(padx=10, pady=10)
        self.cancelBreak.pack(padx=10, pady=10)
        self.sessionControlsHidden = False
        self.breakPromptVisible = True


    def showSessionControls(self):
        # Remove everything first
        self.label.pack_forget()
        self.countdownLabel.pack_forget()
        self.timeFrame.pack_forget()
        self.overlaySwitch.pack_forget()
        self.listMenu.pack_forget()
        self.startButton.pack_forget()
        self.cancelBreak.pack_forget()
        self.breakPromptVisible = False

        # Configure buttons
        self.startButton.bind("<Button-1>", lambda event: self.handleStartStop())

        # Rebuild the normal UI
        self.label.pack(padx=10, pady=10)
        self.countdownLabel.pack(padx=10, pady=5)
        self.timeFrame.pack(padx=0, pady=10)
        self.overlaySwitch.pack(pady=5)
        self.listMenu.pack(padx=10, pady=10)
        self.startButton.pack(padx=10, pady=10)

        self.sessionControlsHidden = False

        self.update_idletasks()

    def rePack(self):
        self.showSessionControls()

class AddApps(tk.Frame):
    def __init__(self, parent, controller, refreshCallback=None):
        tk.Frame.__init__(self, parent)
        self.configure(bg='#111937')
        self.refreshCallback = refreshCallback
        self.listMenu = None

        scroll = ScrollableFrame(self)
        scroll.pack(fill="both", expand=True)

        container = scroll.scrollableFrame

        def center_text(widget):
            widget.tag_add("center", "1.0", "end")

        # Title
        label = ttk.Label(
            container,
            text="Add Apps & Websites",
            font=schoolReallyBigFont,
            background="#111937",
            foreground="#0a7543"
        )
        label.pack(padx=10, pady=10)
        instructions = ttk.Label(
            container,
            text="Type the address of the files you want to block in the textbox below. Use two # surrounding a certain folder path to blacklist the entire folder path. Use two % surrounding a file or folder to whitelist it. By default web extension will block the entirety of that web address. Use !! or #C:/# to block the entire computer, or use two * around any extension type to block that extension type.",
            font=schoolMediumFont,
            background="#111937",
            foreground="#0a7543",
            wraplength=500,
            justify="center"
        )
        instructions.pack(padx=10, pady=5)
        self.instructions = instructions

        warning = ttk.Label(
            container,
            text="Warning: Blocking critical system files or folders may cause system instability. Be cautious when blocking items, especially with broad patterns like !! or #C:/#. Always ensure you have access to unblock if needed.",
            font=schoolMediumFont,
            background="#111937",
            foreground="#a30000",
            wraplength=500,
            justify="center"
        )
        warning.pack(padx=10, pady=5)
        self.warning = warning

        mainExeDir = os.path.dirname(sys.executable)
        blockingExe = os.path.join(mainExeDir, "startBlocking.exe")
        panicExe = os.path.join(mainExeDir, "panic.exe")
        defaultAppText = "Default Values:\n%C:\\Windows%\n%C:\\Windows.~WS%\n%C:\\$WINDOWS.~BT%\n%" + str(sys.executable) + "%" + "\n%" + str(blockingExe) + "% + \n%" + str(panicExe) + "%"
        if platform.system() != "Windows":
            defaultAppText = "Default Values:\n%/usr/bin%\n%/usr/local/bin%\n%/opt%\n/usr/bin/firefox"

        nesText = tk.Label(
            container,
            text=defaultAppText,
            font=schoolBigFont,
            background="#466d72",
            foreground="#454545",
            width=31,
            wraplength=420,
            justify="left")
        nesText.pack(padx = 10, pady=10)

        # ---- APPS BOX ----
        apps_label = tk.Label(
            container,
            text="Apps",
            font=schoolBigFont,
            background="#111937",
            foreground="#0a7543"
        )
        apps_label.pack(padx=10, pady=5)

        self.app_input = tk.Text(
            container,
            width=35,
            height=5,
            font=schoolBigFont,
            background="#466d72",
            foreground="#172D11"
        )
        self.app_input.pack(padx=10, pady=10)
        self.app_input.tag_configure("center", justify='center')
        self.app_input.bind("<KeyRelease>", lambda e: center_text(self.app_input))

        # ---- WEBSITES BOX ----
        web_label = tk.Label(
            container,
            text="Websites",
            font=schoolBigFont,
            background="#111937",
            foreground="#0a7543"
        )
        web_label.pack(padx=10, pady=5)

        self.web_input = tk.Text(
            container,
            width=35,
            height=5,
            font=schoolBigFont,
            background="#466d72",
            foreground="#172D11"
        )
        self.web_input.pack(padx=10, pady=10)
        self.web_input.tag_configure("center", justify='center')
        self.web_input.bind("<KeyRelease>", lambda e: center_text(self.web_input))

        nameLabel = tk.Label(
            container,
            text="List Name (for saving)",
            font=schoolBigFont,
            background="#111937",
            foreground="#0a7543"
        )
        nameLabel.pack(padx=10, pady=5)

        self.nameInput = tk.Entry(
            container,
            width=20,
            font=schoolBigFont,
            background="#466d72",
            foreground="#111937",
            justify="center")
        self.nameInput.pack(padx=10, pady=10)

        # ---- BUTTON ROW ----
        button_frame = tk.Frame(container, bg="#111937")
        button_frame.pack(padx=0, pady=0)

        # ---- SAVE BUTTON ----
        saveButton = tk.Label(
            button_frame,
            text="Save",
            activebackground="#0a7543",
            activeforeground="#111937",
            anchor="center",
            bd=3,
            bg="#0a7543",
            cursor="hand2",
            fg="#111937",
            font=schoolBigFont,
            justify="center",
            width=10
        )
        saveButton.bind("<Button-1>", lambda event: saveList(self.app_input, self.web_input, self.nameInput, self.refreshCallback))
        saveButton.grid(padx=10, pady=10, column=0, row=0)

        # ---- DROPDOWN ----
        self.listMenu = tk.Menubutton(
            button_frame,
            text="Saved Lists",
            bg="#DFF1DA",
            font=schoolBigFont,
            fg="#172D11",
            width=10,
            activebackground="#DFF1DA",
            cursor="hand2",
        )

        self.listMenu.menu = tk.Menu(self.listMenu, tearoff=0)
        self.listMenu["menu"] = self.listMenu.menu

        self._populateListMenu()

        self.listMenu.grid(padx=10, pady=10, column=1, row=0)
    
        deleteButton = tk.Label(
            container,
            text="Delete",
            activebackground="#a30000",
            activeforeground="#ffffff",
            anchor="center",
            bd=3,
            bg="#a30000",
            cursor="hand2",
            fg="#ffffff",
            font=schoolBigFont,
            justify="center",
            width=10
        )
        deleteButton.bind("<Button-1>", lambda event: deleteList(self.nameInput.get(), self.refreshCallback))
        deleteButton.pack(padx=10, pady=10)

    def handleResponsiveResize(self, scale, windowWidth):
        wrapLength = max(280, round(min(windowWidth - 40, 500 * scale)))
        self.instructions.configure(wraplength=wrapLength)
        self.warning.configure(wraplength=wrapLength)
        textWidth = max(24, round(35 * scale))
        textHeight = max(4, round(5 * scale))
        self.app_input.configure(width=textWidth, height=textHeight)
        self.web_input.configure(width=textWidth, height=textHeight)
        self.nameInput.configure(width=max(14, round(20 * scale)))


    def _populateListMenu(self):
        """
        Populate the list menu dropdown with available lists."""
        self.listMenu.menu.delete(0, 'end')
        for i in scanForAppListFile(getAppListPath()):
            self.listMenu.menu.add_command(
                label=i,
                command=lambda i=i: self.load_list(i, self.app_input, self.web_input, self.nameInput),
                background="#DFF1DA",
                font=schoolSmallFont,
                foreground="#172D11",
            )
    def refreshListMenu(self):
        """
        Refresh the list menu dropdown when lists are added or deleted.
        """
        if self.listMenu:
            self._populateListMenu()

    def load_list(self, name, app_input, web_input, nameInput):
        data = turnToReadableDictonary(getAppListPath(), name)

        # Clear both boxes
        app_input.delete("1.0", "end")
        web_input.delete("1.0", "end")
        nameInput.delete(0, "end")

        # Modifier mappings
        modifierSymbols = {"blackList": "#", "extensionBlock": "*", "whiteList": "%"}

        # Fill Apps
        if "Apps" in data:
            appLines = []
            for app, modifierType in data["Apps"].items():
                if modifierType in modifierSymbols:
                    symbol = modifierSymbols[modifierType]
                    appLines.append(f"{symbol}{app}{symbol}")
                else:
                    appLines.append(app)
            app_input.insert("1.0", "\n".join(appLines))

        # Fill Websites
        if "Websites" in data:
            websiteLines = []
            for website, modifierType in data["Websites"].items():
                if modifierType in modifierSymbols:
                    symbol = modifierSymbols[modifierType]
                    websiteLines.append(f"{symbol}{website}{symbol}")
                else:
                    websiteLines.append(website)
            web_input.insert("1.0", "\n".join(websiteLines))
        
        nameInput.insert(0, name)

        # Center text
        app_input.tag_add("center", "1.0", "end")
        web_input.tag_add("center", "1.0", "end")

if __name__ == "__main__":
    if isBlockingMode():
        runBlockingMode()
    else:
        app = tkinterApp()
        app.mainloop()