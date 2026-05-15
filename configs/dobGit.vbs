' dobGit.vbs
' Continuously running script that triggers the Python updater every day at 5:00 AM

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonScript = fso.BuildPath(scriptDir, "git_updater\git_update.py")

Do
    nowTime = Now
    ' Target time is today at 5:00 AM
    targetTime = DateValue(nowTime) + TimeValue("05:00:00")
    
    ' If it's already past 5:00 AM today, schedule for tomorrow at 5:00 AM
    If nowTime >= targetTime Then
        targetTime = targetTime + 1
    End If
    
    ' Calculate seconds until the target time
    diffSeconds = DateDiff("s", nowTime, targetTime)
    
    ' Sleep until that time (WScript.Sleep takes milliseconds)
    ' We loop sleep in chunks of 1 hour to prevent any potential overflow issues
    ' with extremely large numbers in WScript.Sleep, though usually fine up to ~24 days
    
    msToSleep = diffSeconds * 1000
    
    ' Just sleep the whole duration
    WScript.Sleep msToSleep
    
    ' After waking up, run the python update script silently
    ' 0 means hidden window, True means wait for it to finish
    shell.Run "pythonw """ & pythonScript & """", 0, True
Loop
