@echo off

cd test_scripts

start cmd /k ( color 0C ^& "libtest - listen msg.py" local.tcp.5678 )

start cmd /k ( color 0D ^& "libtest - listen msg.py" local.udp.6789 )
ping -n 5 127.0.0.1 >NUL
start cmd /k ( color 0D ^& "libtest - listen msg.py" local.udp.6789 )

rem start cmd /k ( color 0E ^& "libtest - listen msg.py" bad.transport ^& title bad.transport )

start cmd /k ( color 0F ^& "libtest - listen msg.py" local.tcp.7900.tokill )
ping -n 5 127.0.0.1 >NUL
start cmd /k ( color 0F ^& "libtest - listen msg.py" local.tcp.7900.tokill )

start cmd /k ( color 0A ^& "libtest - listen msg.py" local.tcp.7800.unicode )

:end