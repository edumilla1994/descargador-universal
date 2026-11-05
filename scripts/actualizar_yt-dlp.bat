@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo Actualizando yt-dlp a la ultima version...
echo.
python "%~dp0..\descargar.py" --actualizar
echo.
echo Listo. Cierra esta ventana.
pause
