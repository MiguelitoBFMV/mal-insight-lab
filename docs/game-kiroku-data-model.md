# Game Kiroku — Modelo de datos y arquitectura del MVP

Este documento describe el estado implementado de **Game Kiroku / ゲーム記録** dentro de MVS Tracker.

Ya no corresponde a un diseño previo a migraciones. La arquitectura aquí documentada refleja el módulo operativo en el punto de control actual, con esquema aplicado hasta `games.0007_franchise_logo_url` y una suite global de **126 pruebas aprobadas**.

El MVP se encuentra en su etapa final. Los grandes bloques ya implementados son:

- Biblioteca personal.
- Wishlist y propiedad por plataforma.
- Playthroughs y replays.
- Accesos y tiendas.
- Metadatos locales importados desde IGDB.
- Contenido adicional.
- Platinum Collection.
- Franquicias y cronologías.
- Acceso público de solo lectura.
- Administración privada desde la propia interfaz.

Los bloques restantes para declarar el MVP completo son Competitive Rank Tracking y el hardening final.

---

## 1. Principios de arquitectura

Game Kiroku sigue estos principios:

- Los metadatos externos se importan y almacenan localmente.
- IGDB no es una dependencia necesaria para cargar páginas normales.
- Los datos de la obra se separan de la relación personal con ella.
- Una obra no se duplica por plataforma.
- La propiedad y la wishlist se expresan mediante accesos.
- Los playthroughs representan recorridos individuales.
- El progreso es opcional y manual.
- El platino pertenece a la entrada personal completa, no a una plataforma.
- Las franquicias se organizan manualmente.
- El MVP trabaja con una única biblioteca personal.
- Los modelos de Game Kiroku no se relacionan con `User`.
- La autenticación determina quién puede escribir.
- Las vistas públicas son de solo lectura.
- Las acciones mutables requieren normalmente login, POST y CSRF.
- Los GET normales no producen sincronizaciones ni escrituras ocultas.

---

## 2. Modelo conceptual implementado

```text
Franchise
    └── Game
          └── LibraryEntry
                ├── GameAccess
                │      └── Playthrough opcionalmente
                ├── Playthrough
                └── GameContent
```

### Responsabilidad de cada entidad

```text
Franchise
    Agrupa manualmente juegos de una misma saga y define
    su identidad visual.

Game
    Representa el videojuego como obra y almacena
    metadatos locales o importados desde IGDB.

LibraryEntry
    Representa la relación personal con el videojuego.

GameAccess
    Representa dónde se posee o se desea adquirir
    el videojuego.

Playthrough
    Representa cada recorrido individual realizado
    sobre el videojuego.

GameContent
    Representa DLC, expansiones y otros contenidos
    relacionados que no necesitan convertirse en
    juegos independientes de la biblioteca.
```

---

## 3. Franchise

`Franchise` agrupa manualmente juegos de una misma saga.

Ejemplos reales:

- Assassin's Creed.
- Yakuza / Like a Dragon.
- Final Fantasy.
- Persona.
- Ratchet & Clank.
- Grand Theft Auto.

Un juego puede pertenecer a una franquicia o quedar sin agrupar.

### Campos implementados

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `name` | `CharField` | No | Nombre visible y único. |
| `slug` | `SlugField` | No | Identificador estable y único para URL. |
| `description` | `TextField` | Sí | Descripción opcional. |
| `logo_url` | `URLField` | Sí | Logo o imagen representativa opcional. |
| `display_order` | `PositiveIntegerField` | No | Orden manual. |
| `created_at` | `DateTimeField` | No | Fecha de creación. |
| `updated_at` | `DateTimeField` | No | Última modificación. |

### Reglas

- `name` es único.
- `slug` es único.
- El slug se genera una sola vez y se conserva aunque cambie el nombre visible.
- La relación con `Game` es opcional.
- Una franquicia vacía puede eliminarse.
- Una franquicia con juegos asignados no puede eliminarse.
- El owner puede ver y administrar franquicias vacías.
- Los visitantes solo ven franquicias que ya contienen juegos.

### Identidad visual

La franquicia puede tener un `logo_url` manual.

El fondo se deriva automáticamente de un juego representativo. Se usa:

```text
artwork_url
    si existe

cover_url
    como fallback
```

La prioridad de estado para elegir el juego representativo es:

```text
1. Playing
2. Completed
3. Paused
4. Multiplayer
5. Plan to Play
6. Dropped
```

Cuando varios juegos comparten prioridad, se prefiere el actualizado más recientemente.

### Vistas

```text
/games/franchises/
/games/franchises/<slug>/
```

La ficha muestra:

- Hero con imagen dinámica.
- Logo opcional.
- Descripción.
- Juego representativo.
- Progreso porcentual.
- Total, Owned, Active, Plan to Play, Completed y Platinum.
- Cronología por lanzamiento.
- Orden antiguo → nuevo o nuevo → antiguo.
- `Add Game` para volver a Library.
- Controles privados de edición.

---

## 4. Game

`Game` representa el videojuego como obra.

No contiene estados personales como Playing, Completed o Wishlist.

### Campos implementados

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `igdb_id` | `PositiveBigIntegerField` | Sí | Identificador externo único de IGDB. |
| `title` | `CharField` | No | Título principal. |
| `title_japanese` | `CharField` | Sí | Título japonés opcional. |
| `slug` | `SlugField` | No | Identificador local estable y único. |
| `summary` | `TextField` | Sí | Sinopsis local. |
| `cover_url` | `URLField` | Sí | Portada vertical. |
| `artwork_url` | `URLField` | Sí | Imagen horizontal o de fondo. |
| `first_release_date` | `DateField` | Sí | Primera fecha de lanzamiento conocida. |
| `igdb_main_story_hours` | `DecimalField` | Sí | Estimación Main Story importada. |
| `genres` | `JSONField` | Sí | Géneros importados. |
| `platforms` | `JSONField` | Sí | Plataformas importadas. |
| `igdb_payload` | `JSONField` | Sí | Payload normalizado o relevante de IGDB. |
| `igdb_synced_at` | `DateTimeField` | Sí | Último refresh explícito. |
| `franchise` | `ForeignKey` | Sí | Franquicia manual opcional. |
| `created_at` | `DateTimeField` | No | Fecha de creación local. |
| `updated_at` | `DateTimeField` | No | Última modificación. |

### Reglas

- `igdb_id` es único cuando existe.
- Se permiten juegos manuales sin `igdb_id`.
- `slug` es único y estable.
- `igdb_main_story_hours` debe ser positivo.
- Solo se utiliza la estimación **Main Story**.
- No se incorporan Main + Extra ni Completionist en el MVP.
- Existe un índice por `title`.
- La biblioteca carga desde PostgreSQL, no desde IGDB.
- La franquicia puede asignarse durante la importación o desde Game Detail.

### Importación local-first

IGDB se utiliza únicamente mediante acciones explícitas del owner:

```text
Search
Review
Import
Link existing
Refresh metadata
Detect related content
```

El importador puede:

- Vincular metadata a un juego local existente sin reemplazar su PK, slug, estado, accesos, playthroughs o notas.
- Crear transaccionalmente un `Game`, `LibraryEntry` y `GameAccess`.
- Asignar una franquicia existente durante el import.
- Registrar Platinum, fecha de Platinum o Platinum Target.
- Guardar payload y timestamp localmente.

---

## 5. LibraryEntry

`LibraryEntry` representa la relación personal con un videojuego.

Cada `Game` puede tener como máximo una entrada.

### Estados implementados

```text
playing
paused
dropped
plan_to_play
completed
multiplayer
```

### Campos implementados

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `game` | `OneToOneField` | No | Juego asociado. |
| `status` | `CharField` | Sí | Estado personal general. |
| `has_platinum` | `BooleanField` | No | Platino obtenido. |
| `platinum_earned_on` | `DateField` | Sí | Fecha opcional de obtención. |
| `is_platinum_target` | `BooleanField` | No | Objetivo futuro de platino. |
| `main_story_hours_override` | `DecimalField` | Sí | Duración manual. |
| `notes` | `TextField` | Sí | Notas personales. |
| `created_at` | `DateTimeField` | No | Fecha de incorporación. |
| `updated_at` | `DateTimeField` | No | Último cambio. |

### Reglas de estado

- Sin playthroughs, el owner puede seleccionar estados manuales compatibles.
- Playing y Paused requieren un playthrough.
- Cuando existen playthroughs, el estado de biblioteca queda controlado por su historial.
- Multiplayer no utiliza playthroughs.
- Multiplayer debe conservar al menos un acceso Owned.
- Multiplayer no utiliza duración Main Story manual.

### Reglas de platino

- El platino pertenece a `LibraryEntry`, no a `GameAccess`.
- Un platino requiere al menos un acceso Owned.
- `platinum_earned_on` requiere `has_platinum=True`.
- Un juego con platino no puede permanecer como Platinum Target.
- Al quitar el platino desde el formulario, su fecha se limpia.
- Un juego poseído actualmente en PC puede marcarse como Platinum Target aunque el objetivo futuro sea conseguirlo en PS5.
- El último acceso Owned no puede degradarse cuando la entrada conserva platino.

### Duración efectiva

```text
main_story_hours_override
        si existe

igdb_main_story_hours
        en caso contrario
```

### Propiedades derivadas

```python
effective_main_story_hours
is_owned
is_wishlisted
```

---

## 6. Platinum Collection

El sistema de platino se apoya en `LibraryEntry`.

Ruta:

```text
/games/platinum/
```

La colección muestra:

- Total de platinos.
- Último platino con fecha conocida.
- Historial agrupado por año.
- Platinos con fecha desconocida.
- Platinum Targets.
- Portadas y navegación a Game Detail.

La biblioteca ofrece filtros para:

```text
Platinum Unlocked
Platinum Target
```

Los platinos desbloqueados se ordenan por:

```text
fecha de obtención más reciente
        ↓
fecha de obtención más antigua
        ↓
fecha desconocida al final
```

---

## 7. GameAccess

`GameAccess` representa dónde se posee o se desea adquirir un juego.

El juego no se duplica por plataforma.

### Tipos

```text
owned
wishlist
```

### Plataformas implementadas

```text
pc
ps5
switch_2
other
```

### Tiendas implementadas

```text
steam
epic_games
playstation_store
nintendo_eshop
gog
other
```

### Campos implementados

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `library_entry` | `ForeignKey` | No | Entrada personal asociada. |
| `access_type` | `CharField` | No | Owned o Wishlist. |
| `platform_name` | `CharField` | No | Plataforma. |
| `store` | `CharField` | Sí | Tienda. |
| `notes` | `TextField` | Sí | Contexto adicional. |
| `created_at` | `DateTimeField` | No | Fecha de creación. |
| `updated_at` | `DateTimeField` | No | Última modificación. |

### Reglas

Se evita duplicar exactamente:

```text
library_entry
access_type
platform_name
store
```

Un juego puede tener:

- Varios accesos Owned.
- Varios accesos Wishlist.
- Owned y Wishlist en ubicaciones diferentes.
- Owned y Wishlist en una misma plataforma cuando representan accesos distintos.

### Integridad histórica

Un acceso usado por un playthrough:

- No puede eliminarse.
- Debe permanecer Owned.
- Bloquea edición de tipo, plataforma y tienda.
- Permite seguir editando sus notas.

Esta regla evita reescribir retroactivamente la plataforma histórica de un playthrough.

---

## 8. Playthrough

`Playthrough` representa cada recorrido individual.

### Estados

```text
playing
paused
completed
dropped
```

### Idiomas de texto

```text
ja
en
es
other
```

Las voces no se registran en el MVP.

### Campos implementados

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `library_entry` | `ForeignKey` | No | Entrada personal. |
| `access` | `ForeignKey` | Sí | Acceso Owned utilizado. |
| `number` | `PositiveIntegerField` | No | Número del recorrido. |
| `status` | `CharField` | No | Estado del recorrido. |
| `text_language` | `CharField` | No | Idioma principal del texto. |
| `started_on` | `DateField` | Sí | Fecha de inicio. |
| `finished_on` | `DateField` | Sí | Fecha de término. |
| `progress_note` | `CharField` | Sí | Progreso manual libre. |
| `hours_played` | `DecimalField` | Sí | Duración real opcional. |
| `notes` | `TextField` | Sí | Contexto o impresiones. |
| `created_at` | `DateTimeField` | No | Fecha de creación. |
| `updated_at` | `DateTimeField` | No | Última modificación. |

### Reglas

- `number` es único dentro de una `LibraryEntry`.
- `number >= 1`.
- `finished_on >= started_on`.
- `hours_played > 0` cuando existe.
- El acceso debe pertenecer a la misma entrada.
- El selector ofrece únicamente accesos Owned de esa entrada.
- Un playthrough Playing o Paused no puede tener fecha de término.
- Los juegos Multiplayer no aceptan playthroughs.

### Creación y transiciones

Al iniciar un nuevo playthrough:

- Se asigna automáticamente el siguiente número.
- Se usa la fecha local cuando no se entrega una explícita.
- Otro playthrough activo de la misma entrada se pausa.
- La `LibraryEntry` pasa a Playing.

Las acciones disponibles son:

```text
pause
resume
complete
drop
```

Las transiciones actualizan el playthrough y la entrada de biblioteca de forma coordinada.

### Progreso válido

```text
Chapter 7
Act 2
63%
Main Story completed
Historia principal terminada
```

No existe porcentaje universal ni estimación automática de finalización.

---

## 9. GameContent

`GameContent` registra contenido relacionado bajo una entrada sin inflar el total de juegos de la biblioteca.

### Tipos

```text
dlc
expansion
standalone_expansion
other
```

### Estados

```text
plan_to_play
playing
paused
completed
dropped
```

### Campos implementados

| Campo | Tipo | Nulo / vacío | Descripción |
|---|---|---:|---|
| `library_entry` | `ForeignKey` | No | Juego padre en la biblioteca. |
| `igdb_id` | `PositiveBigIntegerField` | Sí | ID externo único. |
| `title` | `CharField` | No | Título del contenido. |
| `content_type` | `CharField` | No | Tipo de contenido. |
| `status` | `CharField` | No | Estado personal. |
| `summary` | `TextField` | Sí | Sinopsis. |
| `cover_url` | `URLField` | Sí | Portada. |
| `first_release_date` | `DateField` | Sí | Fecha de lanzamiento. |
| `completed_on` | `DateField` | Sí | Fecha opcional de término. |
| `notes` | `TextField` | Sí | Notas personales. |
| `igdb_payload` | `JSONField` | Sí | Payload almacenado. |
| `created_at` | `DateTimeField` | No | Fecha de creación. |
| `updated_at` | `DateTimeField` | No | Último cambio. |

### Reglas

- `igdb_id` es único cuando existe.
- El título es único dentro del mismo juego padre.
- `completed_on` solo es válido con estado Completed.
- Puede crearse manualmente.
- Puede derivarse de contenido detectado en el payload IGDB.
- El owner puede editarlo o eliminarlo.

### Relaciones IGDB detectadas

```text
dlcs
expansions
standalone_expansions
parent_game
```

Una obra detectada puede:

- Registrarse como `GameContent`.
- Revisarse como juego independiente.
- Enlazar a un `Game` local ya importado cuando corresponde.

---

## 10. Restricciones y validaciones

### Restricciones de base de datos

Se encuentran implementadas restricciones para:

- `Game.igdb_id` único.
- `Game.slug` único.
- `Franchise.name` único.
- `Franchise.slug` único.
- Un `LibraryEntry` por `Game`.
- Horas Main Story positivas.
- Duración manual positiva.
- Horas de playthrough positivas.
- Número de playthrough positivo.
- Número único por entrada.
- Rango válido de fechas del playthrough.
- Accesos exactos no duplicados.
- Título de GameContent único dentro del padre.
- Fecha de GameContent coherente con Completed.
- Fecha de Platinum coherente con Platinum Unlocked.
- Platinum Target incompatible con Platinum Unlocked.

### Validación de formularios y servicios

Se validan además:

- Acceso del playthrough perteneciente a la misma entrada.
- Playing y Paused dependientes de playthroughs.
- Estados y fechas coherentes.
- Multiplayer sin Main Story manual.
- Multiplayer con acceso Owned.
- Platinum con acceso Owned.
- Conservación del último Owned de una entrada con Platinum.
- Identidad histórica bloqueada para accesos en uso.
- Eliminación de franquicia solo cuando está vacía.
- URLs de logo válidas.
- Asignación de franquicia a juegos existentes o importados.
- Transiciones válidas de playthrough.

---

## 11. Relaciones Django

```text
Franchise.games
Game.library_entry
Game.franchise
LibraryEntry.accesses
LibraryEntry.playthroughs
LibraryEntry.additional_contents
GameAccess.playthroughs
Playthrough.library_entry
Playthrough.access
GameContent.library_entry
```

---

## 12. Flujos principales

### Importar un juego desde IGDB

```text
Buscar en IGDB
        ↓
Revisar título o edición
        ↓
Elegir estado y franquicia opcional
        ↓
Elegir acceso inicial
        ↓
Guardar Game localmente
        ↓
Crear LibraryEntry
        ↓
Crear GameAccess
```

### Vincular un juego local

```text
Seleccionar resultado IGDB
        ↓
Elegir Game local sin IGDB
        ↓
Actualizar metadata del Game
        ↓
Conservar PK, slug, LibraryEntry,
accesos, playthroughs, estado y notas
```

### Administrar una franquicia

```text
Crear Franchise
        ↓
Agregar descripción y logo opcional
        ↓
Asignar juegos desde Game Detail
o durante importación
        ↓
Consultar progreso y timeline
        ↓
Mover o retirar juegos cuando sea necesario
```

### Registrar un playthrough

```text
Abrir Game Detail
        ↓
Seleccionar acceso Owned
        ↓
Crear Playthrough
        ↓
Asignar número automático
        ↓
Indicar idioma y fecha
        ↓
Actualizar progreso y estado
```

### Registrar contenido adicional

```text
Abrir Game Detail
        ↓
Revisar contenido detectado por IGDB
        ↓
Track Under This Game
o
Review as Separate Game
```

---

## 13. Métricas actuales y futuras

### Implementadas

- Total de biblioteca.
- Owned.
- Wishlist.
- Completed.
- Plan to Play.
- Multiplayer.
- Platinum.
- Progreso por franquicia.
- Owned por franquicia.
- Completed por franquicia.
- Platinum por franquicia.
- Último Platinum.
- Historial de Platinum por año.
- Platinum Targets.
- Replay-aware completion.

### Posteriores al MVP

- Tiempo real por juego y franquicia.
- Diferencia entre tiempo estimado y real.
- Distribución por idioma.
- Analítica avanzada por plataforma y tienda.
- Tendencias temporales conectadas con Hibi Log.

---

## 14. Competitive Rank Tracking pendiente

El último gran sistema funcional del MVP será el seguimiento competitivo manual.

Debe permitir configuraciones específicas por juego.

Ejemplo Rocket League:

```text
1v1
2v2
3v3
```

Cada modo podrá registrar:

- Temporada.
- Rango.
- División.
- Fecha y hora.
- Múltiples movimientos el mismo día.
- Rango actual derivado del último evento.
- Historial de subidas y bajadas.

Battlefield y otros juegos reutilizarán la infraestructura, pero no compartirán necesariamente modos, rangos ni divisiones.

---

## 15. Integración futura con Hibi Log

Hibi Log podrá relacionar actividad con:

- `LibraryEntry`.
- `Playthrough`.
- `GameAccess` cuando aporte contexto.
- `GameContent` cuando la sesión corresponda a DLC o expansión.

Ejemplo conceptual:

```text
ActivitySession
library_entry: Yakuza Kiwami 2
playthrough: Playthrough 2
duration_minutes: 95
progress_from: Chapter 6
progress_to: Chapter 7
notes: Sesión de historia principal en japonés
```

Game Kiroku ya expone identificadores estables para permitir esta integración futura.

---

## 16. Decisiones fuera del MVP

No se incluyen dentro del MVP:

- Main + Extra y Completionist.
- Voces o doblaje por playthrough.
- Porcentaje universal de progreso.
- Estimación automática de finalización.
- Trofeos individuales.
- Logros de Steam.
- Distinción física, digital o suscripción.
- Múltiples usuarios.
- Sincronización permanente con IGDB.
- Duplicación del juego por plataforma.
- Relaciones de franquicia importadas automáticamente.
- APIs externas de ranking competitivo.
- Duración y playthroughs independientes para cada DLC.

---

## 17. Estado de implementación

```text
Documento: game-kiroku-data-model.md
Módulo: Game Kiroku
Etapa: MVP — cierre funcional
Estado: Implementado y aprobado hasta Franchise Views
Migración actual: games.0007_franchise_logo_url
Pruebas globales: 126 OK
Próximo bloque: Competitive Rank Tracking
```

Las migraciones ya fueron creadas y aplicadas. Este documento debe actualizarse nuevamente al incorporar los modelos de Competitive Rank Tracking y al declarar el MVP completo.
