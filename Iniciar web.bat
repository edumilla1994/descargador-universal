@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  Descargador Web
echo  ------------------------------------------------
echo  PC:     http://localhost:8080
echo  Movil:  usa la direccion que aparece abajo (misma Wi-Fi)
echo.
echo  Solo para tu red Wi-Fi. No lo expongas a Internet sin clave.
echo  Cierra esta ventana para detener el servidor.
echo.
python web.py --lan --abrir
echo.
pause
