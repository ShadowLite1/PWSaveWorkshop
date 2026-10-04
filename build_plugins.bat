@echo off
setlocal
set "TASKROOT=%~dp0"
set "TASKVSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%TASKVSWHERE%" exit /b 1
for /f "usebackq tokens=*" %%i in (`"%TASKVSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "TASKVS=%%i"
if not defined TASKVS exit /b 1
call "%TASKVS%\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
if not exist "%TASKROOT%build\plugins" mkdir "%TASKROOT%build\plugins"
if not exist "%TASKROOT%asi" mkdir "%TASKROOT%asi"
pushd "%TASKROOT%build\plugins"
set "TASKMH=%TASKROOT%third_party\minhook"
cl /nologo /O2 /MT /c /I"%TASKMH%\include" "%TASKMH%\src\buffer.c" "%TASKMH%\src\hook.c" "%TASKMH%\src\trampoline.c" "%TASKMH%\src\hde\hde64.c"
if errorlevel 1 goto failed
cl /nologo /std:c++20 /O2 /MT /EHsc /LD "%TASKROOT%plugins\PeaceWalkerSevenSlots.cpp" /link /OUT:"%TASKROOT%asi\PeaceWalkerSevenSlots_v3.asi" /DLL
if errorlevel 1 goto failed
cl /nologo /std:c++20 /O2 /MT /EHsc /LD "%TASKROOT%plugins\PeaceWalkerEightSkills.cpp" /link /OUT:"%TASKROOT%asi\PeaceWalkerEightSkills.asi" /DLL
if errorlevel 1 goto failed
cl /nologo /std:c++20 /O2 /MT /EHsc /LD /I"%TASKMH%\include" "%TASKROOT%plugins\PeaceWalkerCrossBattleInputTest.cpp" buffer.obj hook.obj trampoline.obj hde64.obj /link /OUT:"%TASKROOT%asi\PeaceWalkerCrossBattleInputTest_v1.asi" /DLL
if errorlevel 1 goto failed
cl /nologo /std:c++20 /O2 /MT /EHsc /LD /I"%TASKMH%\include" "%TASKROOT%plugins\PeaceWalkerStrikeTableTest.cpp" buffer.obj hook.obj trampoline.obj hde64.obj /link /OUT:"%TASKROOT%asi\PeaceWalkerStrikeTableTest_v1.asi" /DLL
if errorlevel 1 goto failed
cl /nologo /std:c++20 /O2 /MT /EHsc /LD "%TASKROOT%plugins\PeaceWalkerVersusEquipment.cpp" /link /OUT:"%TASKROOT%asi\PeaceWalkerVersusEquipment_v4.asi" /DLL
if errorlevel 1 goto failed
popd
exit /b 0
:failed
popd
exit /b 1
