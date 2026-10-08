// Arranque de la tienda. Se carga último: para cuando responde el servidor, todos los archivos de la tienda ya están cargados.

brandReady.then(ok => ok && loadEstado().then(openStore).catch(e => e.status === 401 || e.status === 403 ? lockOut(e)
  : Swal.fire({ icon: "error", title: "No se pudo cargar la tienda", text: e.message })));
