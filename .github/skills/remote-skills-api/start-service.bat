@echo off
:: Auto-start Remote Skills API at login
:: Place a shortcut to this in shell:startup, or run install-startup.ps1

cd /d "Z:\Projects\Eric-Cartman"
"C:\Program Files\nodejs\node.exe" ".github\skills\remote-skills-api\server.js"
