(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const formulario = $("formulario");
  const url = $("url");
  const calidad = $("calidad");
  const ganancia = $("ganancia");
  const boton = $("descargar");
  const progreso = $("progreso");
  const relleno = $("relleno");
  const estado = $("estado");
  const cancelar = $("cancelar");
  const resultado = $("resultado");
  const listo = $("listo");
  const enlace = $("enlace");
  const nueva = $("nueva");
  const cajaError = $("error");
  const inicio = $("inicio");

  let jobId = null;
  let timer = null;
  let fallos = 0;

  function mostrarError(texto) {
    cajaError.textContent = texto;
    cajaError.classList.remove("oculto");
  }

  function limpiarError() {
    cajaError.textContent = "";
    cajaError.classList.add("oculto");
  }

  function pararPolling() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  function fallar(texto) {
    pararPolling();
    jobId = null;
    boton.disabled = false;
    cancelar.disabled = false;
    cancelar.classList.add("oculto");
    progreso.classList.add("oculto");
    mostrarError(texto || "No se pudo completar la descarga.");
  }

  function reiniciar() {
    pararPolling();
    jobId = null;
    fallos = 0;
    boton.disabled = false;
    cancelar.disabled = false;
    cancelar.classList.add("oculto");
    progreso.classList.add("oculto");
    resultado.classList.add("oculto");
    relleno.style.width = "0%";
    estado.textContent = "Iniciando...";
    limpiarError();
  }

  async function iniciar(evento) {
    evento.preventDefault();
    if (jobId) return;

    const valor = url.value.trim();
    if (!valor) {
      mostrarError("Pega un enlace primero.");
      url.focus();
      return;
    }

    reiniciar();
    jobId = "pendiente";
    boton.disabled = true;
    progreso.classList.remove("oculto");
    estado.textContent = "Iniciando...";

    try {
      const respuesta = await fetch("/api/descargar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: valor,
          calidad: calidad.value,
          ganancia: parseFloat(ganancia.value),
        }),
      });
      const datos = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        throw new Error(datos.error || "No se pudo iniciar la descarga.");
      }
      jobId = datos.id;
      timer = setInterval(consultar, 1000);
      consultar();
    } catch (err) {
      fallar(err.message || "Error de conexion con el servidor.");
    }
  }

  async function consultar() {
    if (!jobId || jobId === "pendiente") return;
    try {
      const respuesta = await fetch(`/api/estado/${jobId}`, { cache: "no-store" });
      if (respuesta.status === 404) {
        fallar("La descarga ya no existe. Inicia otra.");
        return;
      }
      const datos = await respuesta.json();
      fallos = 0;
      actualizar(datos);
    } catch (err) {
      fallos += 1;
      if (fallos >= 6) {
        fallar("Se perdio la conexion con el servidor local.");
      }
    }
  }

  function actualizar(datos) {
    let pct = datos.pct || 0;
    if (datos.estado === "procesando" || datos.estado === "listo") pct = 100;
    relleno.style.width = `${Math.max(0, Math.min(100, pct))}%`;

    if (datos.estado === "descargando") {
      const velocidad = datos.velocidad ? ` · ${datos.velocidad}` : "";
      estado.textContent = `Descargando... ${Math.round(pct)}%${velocidad}`;
      cancelar.classList.remove("oculto");
    } else if (datos.estado === "procesando") {
      estado.textContent = "Convirtiendo a MP4 y ajustando audio...";
      cancelar.classList.add("oculto");
    } else if (datos.estado === "listo") {
      pararPolling();
      estado.textContent = "Listo.";
      boton.disabled = false;
      cancelar.classList.add("oculto");
      resultado.classList.remove("oculto");
      listo.textContent = `Archivo listo: ${datos.archivo}`;
      enlace.href = `/api/archivo/${jobId}`;
      enlace.download = datos.archivo || "descarga";
      enlace.textContent = `Descargar ${datos.archivo || "archivo"}`;
    } else if (datos.estado === "error") {
      fallar(datos.error || "No se pudo descargar.");
    } else if (datos.estado === "cancelado") {
      fallar("Descarga cancelada.");
    }
  }

  async function cancelarDescarga() {
    if (!jobId || jobId === "pendiente") return;
    cancelar.disabled = true;
    estado.textContent = "Cancelando...";
    try {
      await fetch(`/api/cancelar/${jobId}`, { method: "POST" });
    } catch (err) {
      /* el polling se encarga */
    }
  }

  function nuevaDescarga() {
    reiniciar();
    url.value = "";
    url.focus();
  }

  async function pegar() {
    try {
      const texto = await navigator.clipboard.readText();
      if (texto) {
        url.value = texto.trim();
        url.focus();
      }
    } catch (err) {
      url.focus();
    }
  }

  async function cargarInfo() {
    try {
      const respuesta = await fetch("/api/info", { cache: "no-store" });
      const datos = await respuesta.json();
      $("chip").textContent = datos.local ? "Local" : "Wi-Fi";

      if (datos.lan && datos.local) {
        $("movil").classList.remove("oculto");
        $("url-movil").textContent = `http://${datos.ip}:${datos.puerto}`;
        $("qr").src = "/api/qr";
      }
      if (!datos.local) {
        $("acciones-local").classList.add("oculto");
      } else {
        inicio.checked = Boolean(datos.inicio);
      }
    } catch (err) {
      /* la pagina sigue funcionando */
    }
  }

  async function alternarInicio() {
    const marcado = inicio.checked;
    try {
      const respuesta = await fetch("/api/inicio", {
        method: "POST",
        headers: { "X-Descargador": "1" },
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) throw new Error(datos.error || "No se pudo cambiar.");
      inicio.checked = Boolean(datos.inicio);
    } catch (err) {
      inicio.checked = !marcado;
      mostrarError(err.message || "No se pudo cambiar el inicio automatico.");
    }
  }

  async function detenerServidor() {
    if (!confirm("Se detendra el servidor local. ¿Continuar?")) return;
    try {
      await fetch("/api/detener", {
        method: "POST",
        headers: { "X-Descargador": "1" },
      });
    } catch (err) {
      /* el servidor se apaga igual */
    }
    setTimeout(() => {
      document.querySelector(".tarjeta").innerHTML =
        '<h1>Servidor detenido</h1><p>Puedes cerrar esta pestaña. Para volver a usarlo, abre el acceso directo.</p>';
    }, 900);
  }

  formulario.addEventListener("submit", iniciar);
  $("pegar").addEventListener("click", pegar);
  cancelar.addEventListener("click", cancelarDescarga);
  nueva.addEventListener("click", nuevaDescarga);
  inicio.addEventListener("change", alternarInicio);
  $("detener").addEventListener("click", detenerServidor);

  cargarInfo();
  if (window.matchMedia("(pointer: fine)").matches) {
    url.focus();
  }
})();
