# Calendario Azoteros FC

Calendario de partidos de **Azoteros FC** (Liga Domingo Tarde, Canal Ocio y Deporte) que se actualiza solo desde la web de la liga dos veces al día.

## Suscribirse

**iPhone / Mac:** abre este enlace y pulsa *Suscribirse*:

`webcal://raw.githubusercontent.com/diegoversa/azoteros-calendario/main/azoteros.ics`

Si no se abre al tocarlo: Ajustes → Apps → Calendario → Cuentas → Añadir cuenta → Otra → *Añadir calendario suscrito* y pega el enlace.

**Google Calendar / Android:** en calendar.google.com (ordenador) → *Otros calendarios* → **+** → *Desde URL* y pega:

`https://raw.githubusercontent.com/diegoversa/azoteros-calendario/main/azoteros.ics`

Los cambios (horarios, partidos nuevos, fase final) tardan unas horas en aparecer: depende de cada cuánto refresca tu calendario las suscripciones.

## Cómo funciona

`scrape.py` lee la ficha del equipo y cada partido en ocioydeportecanal.es y regenera `azoteros.ics`. `state.json` guarda los partidos conocidos, porque la ficha solo muestra los próximos cinco. Lo ejecuta una GitHub Action (`.github/workflows/update.yml`), que también se puede lanzar a mano desde la pestaña *Actions* → *Run workflow*.

Si la web falla o cambia de formato, la Action da error y el calendario se queda como estaba; GitHub te avisa por correo.
