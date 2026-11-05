@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "USUARIO=descargador"
if exist web.usuario set /p USUARIO=<web.usuario
set "CLAVE="
if exist web.clave set /p CLAVE=<web.clave
echo.
echo  Descargador Web
echo  ------------------------------------------------
echo  PC:     http://localhost:8080
echo  Movil:  usa la direccion que aparece abajo (misma Wi-Fi)
echo.
echo  Cierra esta ventana para detener el servidor.
echo.
python web.py --lan --abrir --usuario "%USUARIO%" --clave "%CLAVE%"
echo.
pause
