@echo off

cd test_scripts

start cmd /k ( color 20 ^& "libtest - listen msg.py" serial.port.0 ^& exit )

start cmd /k ( color 18 ^& "libtest - listen msg.py" net.tcp ^& exit )

start cmd /k ( color 30 ^& "libtest - listen msg.py" net.udp.7600 ^& exit )

start cmd /k ( color 40 ^& "libtest - listen msg.py" net.multicast.udp.5150 ^& exit )

rem start cmd /k ( color 58 ^& "libtest - listen msg.py" iiiiiiiii ^& exit )
