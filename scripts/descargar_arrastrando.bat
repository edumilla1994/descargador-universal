@echo off
chcp 65001 >nul
cd /d "%~dp0.."
if "%~1"=="" goto pedir
python "%~dp0..\descargar.py" %*
goto fin

:pedir
echo.
echo  Descargador universal (yt-dlp)
echo  ------------------------------------------------
echo  Pega el enlace y pulsa Enter.
echo  Puedes arrastrar un enlace o un archivo de texto aqui.
echo.
set /p URL= Enlace: 
if "%URL%"=="" goto fin
python "%~dp0..\descargar.py" "%URL%"

:fin
echo.
pause
