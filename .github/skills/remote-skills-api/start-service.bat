@echo off
:: Auto-start Remote Skills API at login
:: Place a shortcut to this in shell:startup, or run install-startup.ps1

cd /d "%~dp0..\..\..\.."
node ".github\skills\remote-skills-api\server.js"
