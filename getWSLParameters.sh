# WSL version + Windows build
/mnt/c/Windows/System32/wsl.exe --version
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "[System.Environment]::OSVersion.Version"

# WSL network info
ip addr
ip route

# Windows adapter info (to see Ethernet + modem subnet)
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "Get-NetIPConfiguration | Format-Table -AutoSize"
