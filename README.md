# FocusLock
FocusLock, the all in one solution made entirely to help you focus on the things you care about, written entirely in Python.

Ever feel like you can't focus while trying to work on your computer? Introducing FocusLock, the all in one solution to help you focus on tasks that you actually need to do.

# How To Download
* Either download the entire contents of the dist folder or clone this repo, download all the necessary python extensions and then use pyinstaller and focusLock.spec to create the three apps yourself.
* Place these apps into any folder, just by themselves. The folder can be named anything, but the apps need to be in the same one. Mine are in C:Users/user/Apps/FocusLock
* Launch FocusLock.exe and it will make sure that everything is correct. First it will add a shortcut to the desktop which by default does not have a icon. Use logo.png if you want one. It will also create a folder and a .txt in your documents folder. This is where it will store the things it needs to block.

# How To Use
1. Launch the main app from the desktop shortcut or FocusLock.exe. This will launch the main screen. To keep the app and blocking functionality working properly do not close this main screen. It can be minimized, in the background, on your secondary monitor, whatever. Just don't close it fully unless you want to risk having your apps locked. (In case this does happen see Help! I've locked all my apps!)
2. The default page is called the home page. This is where you'll start focus sessions and choose how long and what focus dictionary to do.
3. The top bar will help you navigate the different pages in the app.
4. For now you'll want to click on Add Sites/Apps so you can edit the blocking list.<img width="962" height="580" alt="Screenshot 2026-09-04 142035" src="https://github.com/user-attachments/assets/eddef13a-90e9-42ed-a745-30cdb158762e" />
5. At the top of the add page there is a blurb telling you the combos you to do advanced blocking, further down there is a text input for the apps you want to block, a input for the sites and then one more input field and three buttons. (Saved Lists is actually a dropdown.)
6. If you want to block sites or apps enter them in their respective fields, making sure when adding sites to include the start of the link (so youtube.com would become https://youtube.com) and when blocking apps when pasting their file names be sure to remove the outer quotations.
7. After your done adding the things you want to block scroll down and enter in a name for the blocking session.
8. Click Save and then when you click Saved Lists there should now be two options, Default and your new list. (If you want you can click on default to see what the list that comes with the app is, you don't need to use it, it's just there and feel free to delete it, as long as you have at least one list in there.)
9. After you have saved your list go back to the home page, where, like I said earlier, is where you start and stop the focus sessions.
10. Make sure to close all all the apps that your blocking, even if their in the background. If you don't bad things will happen. (I don't know exactly what as it depends on the app and what it's doing, so just close them before you block them.)
11. Also close all the tabs for the sites you are planning on blocking, or close your browser. This is because the data from the site's page is stored on your local RAM so when the blocking session starts you'll still be able to access that specific page, until more data from that site is requested, at that point FocusLock will block it.
12. Once you've done the two steps above go back to the app and enter an amount of time you want the focus session to run. There is no maximum time but there is a minimum, you can't enter 0 seconds as a time for there will be no blocking session. You can, however, enter 1 second.
13.  After that click on the thing that says "Using: Default" and then change it to your list choice so it says "Using: (Whatever your list name is)".
14.  There is also a slider that says "Toggle Overlay Timer". Clicking it will launch a little timer in the bottom right of the screen which mirrors the larger timer on the home page. You can move this timer around your screen and it will just be overlayed over all you other apps. This is not necessary but it is nice.
15.  You can now start a focus session by clicking "Start Focus Session" and then allowing FocusLock admin privileges. This is because the command that it runs in order to block your apps and the multiple commands to block the unwanted websites require admin permissions to run, there's just no way around it.
16.  After the focus session is over (Good job! Pat yourself on your back.) you will be presented with an option to do a break session. You do not need to and can close the app, hit "Cancel Break Session" or start a break session. It's up to you.
17.  With FocusLock not being active you can close the app by hitting the exit button on the top right of the menu.

# How Does FocusLock Work?
FocusLock is made using python tkinter which is the general package for building GUIs. The actual code used to block apps is
```python
cmd = ['icacls', path, '/deny', 'Everyone:(F)']
subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
```
and the code to unblock them is
```python
cmd = ['icacls', path, '/grant', 'Everyone:(F)']
subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
```
How blocking sites though is a little more complicated. The basics of it are: Creates a personal server on your computer where it redirects all your computer's network through. In this server it can control what sites get sent through to your computer vs what sites don't. When a site requests to send or receive data the program looks at the list and says "Hmm.. is this a site I can let through?" and if it is not it does not let through the site.
