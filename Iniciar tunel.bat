@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  Tunel Cloudflare para http://localhost:8080
echo  ------------------------------------------------
echo  Copia la URL https://....trycloudflare.com que aparezca abajo.
echo  La web pedira el usuario de web.usuario y la clave de web.clave.
echo  Cierra esta ventana para cortar el tunel.
echo.
bin\cloudflared.exe tunnel --url http://localhost:8080 --no-autoupdate
echo.
pause
