# Checklist de pruebas

## Automaticas

```bash
python -m pytest
```

Cubren:

- Construccion de comandos para cada calidad.
- Cookies de navegador y de archivo `cookies.txt`.
- Playlist y carpeta de salida.
- Comparacion de versiones y deteccion de actualizaciones.
- Motor JavaScript QuickJS cuando no hay Node ni Deno.
- MP4 final con audio AAC y ganancia (prueba de audio).
- Web local: portada, validacion de enlaces, QR, 404 y clave basica.
- Smoke test de la barra: tamano mini/completo, aviso de actualizacion y boton A+.
- Diagnostico del ejecutable empaquetado (si existe `dist/Descargador/Descargador.exe`).

## Windows (probado)

- [x] Compila el ejecutable con PyInstaller.
- [x] Compila el instalador con Inno Setup.
- [x] Instalacion silenciosa en carpeta limpia.
- [x] `Descargador.exe --diagnostico` muestra `Empaquetado: True`, yt-dlp, ffmpeg y QuickJS.
- [x] Descarga real de YouTube empaquetada **sin Node** en el PATH (usa QuickJS).
- [x] Descarga real de Facebook Reel.
- [x] Descarga real de TikTok.
- [x] Descarga real de X (Twitter).
- [x] Audio MP3 con caratula.
- [x] Video final en MP4 (H.264 + AAC) con ganancia +100%.
- [x] Audio MP3 con ganancia +100% (volumedetect: +6 dB, sin clipping).
- [x] Conversion de WebM/AV1 a MP4.
- [x] Boton A+ cicla Normal, +50%, +100% y +200%, y se guarda.
- [x] Desinstalacion limpia.
- [x] Arranque de la barra y captura visual.

## Ubuntu 22.04 (probado)

- [x] Build del `.deb` dentro de Docker.
- [x] Instalacion con `apt install ./descargador_1.1.0_amd64.deb` (resuelve ffmpeg).
- [x] `Descargador --diagnostico` dentro del `.deb`.
- [x] Descarga real de YouTube desde el `.deb` con QuickJS.
- [x] MP4 final y ganancia +100% desde el `.deb` (sin Node).
- [x] Arranque de la GUI con Xvfb durante 5 segundos sin errores.
- [x] `.desktop`, icono y lanzador `/usr/bin/descargador` instalados.

## Web local (probado)

- [x] Descarga real por la API: MP4 H.264/AAC con ganancia +100%.
- [x] Progreso, conversion y enlace de descarga.
- [x] Diseno responsive (escritorio 900px y movil 500px).
- [x] URL de Wi-Fi y codigo QR.
- [x] Acceso desde la IP LAN del PC.
- [x] Proteccion con clave basica (401 sin clave, 200 con clave).
- [x] Iniciar con Windows y detener servidor.

## Tunel Cloudflare (probado)

- [x] Link publico `https://....trycloudflare.com`.
- [x] 401 sin clave y 200 con la clave correcta.
- [x] Los controles de "Iniciar con Windows" y "Detener servidor" quedan bloqueados desde el tunel.
- [x] Descarga real a traves del tunel: MP4 H.264/AAC.
- [x] La URL cambia al reiniciar el tunel (documentado).

## Tailscale Funnel (probado)

- [x] Funnel activo en `https://<maquina>.<tailnet>.ts.net`.
- [x] 401 sin clave y 200 con el usuario/clave configurados.
- [x] Los controles locales quedan bloqueados desde el link publico.
- [x] Descarga real a traves del link fijo: MP4 H.264/AAC.
- [x] Cloudflare apagado; queda solo el link fijo.

## Pendiente

- [ ] Probar el `.dmg` en un Mac real (el script de build esta listo).
- [ ] Probar en una maquina Windows sin Python instalado (el ejecutable es autocontenido, pero conviene verificarlo en una VM limpia).
- [ ] Probar cookies reales de Firefox en Facebook/Instagram privados.
- [ ] Verificar la actualizacion automatica cuando salga una version nueva de yt-dlp.
- [ ] Revisar SmartScreen en la primera descarga del instalador.
