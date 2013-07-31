@echo off
echo.
if exist "C:\python23\Lib\pydoc.py"              set pydoc=C:\python23\Lib\pydoc.py
if exist "%ProgramFiles%\python23\Lib\pydoc.py"  set pydoc=%ProgramFiles%\python23\Lib\pydoc.py
if exist "C:\python26\Lib\pydoc.py"              set pydoc=C:\python26\Lib\pydoc.py
if exist "%ProgramFiles%\python26\Lib\pydoc.py"  set pydoc=%ProgramFiles%\python26\Lib\pydoc.py

echo Using: "%pydoc%"
echo.

"%pydoc%" -w scws
if errorlevel 1 pause

"%pydoc%" -w soaplib
if errorlevel 1 pause
 
