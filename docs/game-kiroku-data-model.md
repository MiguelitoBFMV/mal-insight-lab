# Game Kiroku — Modelo de datos del MVP

Este documento define la arquitectura inicial del módulo **Game Kiroku / ゲーム記録** dentro de MVS Tracker.

El objetivo es establecer una base estable para:

- Biblioteca personal de videojuegos.
- Wishlist.
- Plataformas y tiendas.
- Playthroughs.
- Idiomas de texto.
- Progreso manual.
- Franquicias.
- Platinos.
- Metadatos importados desde IGDB.
- Futuras sesiones de actividad conectadas con Hibi Log.

Esta arquitectura debe revisarse antes de crear la primera migración del módulo `games`.

---

## 1. Principios del modelo

Game Kiroku seguirá estos principios:

- Los metadatos externos se importan y almacenan localmente.
- IGDB no será una dependencia necesaria para cargar la biblioteca.
- Los datos del videojuego se separan de la relación personal del usuario con ese juego.
- Una misma obra no debe duplicarse por plataforma.
- La propiedad y la wishlist se representan por acceso y plataforma.
- Los playthroughs representan recorridos individuales.
- El progreso será opcional y manual.
- El platino pertenece a la entrada personal del juego, no a una plataforma.
- El MVP maneja una sola biblioteca personal.
- La autenticación controla quién puede modificar los datos.
- No habrá relación con el modelo `User` en esta primera versión.

---

## 2. Modelo conceptual

```text
Franchise
    └── Game
          └── LibraryEntry
                ├── GameAccess
                └── Playthrough
                       └── GameAccess opcional
```

### Responsabilidad de cada entidad

```text
Franchise
    Agrupa manualmente juegos de una misma saga.

Game
    Representa el videojuego como obra y almacena sus metadatos.

LibraryEntry
    Representa la relación personal con el videojuego.

GameAccess
    Representa dónde se posee o se desea adquirir el videojuego.

Playthrough
    Representa cada recorrido individual realizado sobre el videojuego.
```

---

## 3. Franchise

Agrupación manual para sagas como:

- Yakuza / Like a Dragon.
- Battlefield.
- Batman Arkham.
- Horizon.
- Persona.
- Final Fantasy.

Un juego puede pertenecer a una franquicia o quedar sin agrupar.

### Campos propuestos

| Campo | Tipo sugerido | Requerido | Descripción |
|---|---|---:|---|
| `name` | `CharField` | Sí | Nombre visible de la franquicia. |
| `slug` | `SlugField` | Sí | Identificador único para futuras URLs. |
| `description` | `TextField` | No | Nota o descripción opcional. |
| `display_order` | `PositiveIntegerField` | Sí | Orden manual en vistas y análisis. |
| `created_at` | `DateTimeField` | Sí | Fecha de creación. |
| `updated_at` | `DateTimeField` | Sí | Última modificación. |

### Reglas

- `name` debe ser único.
- `slug` debe ser único.
- `display_order` puede comenzar en `0`.
- La relación con `Game` será opcional.

### Ejemplo

```text
Franchise
name: Yakuza / Like a Dragon
slug: yakuza-like-a-dragon
display_order: 1
```

---

## 4. Game

Representa el videojuego como obra.

Almacena metadatos importados desde IGDB o ingresados manualmente. No contiene estados personales como `playing`, `completed` o `wishlist`.

### Campos propuestos

| Campo | Tipo sugerido | Requerido | Descripción |
|---|---|---:|---|
| `igdb_id` | `PositiveBigIntegerField` | No | ID externo único de IGDB. |
| `title` | `CharField` | Sí | Título principal del juego. |
| `title_japanese` | `CharField` | No | Título japonés opcional. |
| `slug` | `SlugField` | Sí | Identificador para futuras URLs. |
| `summary` | `TextField` | No | Descripción del juego. |
| `cover_url` | `URLField` | No | Portada vertical. |
| `artwork_url` | `URLField` | No | Imagen horizontal o de fondo. |
| `first_release_date` | `DateField` | No | Primera fecha de lanzamiento. |
| `igdb_main_story_hours` | `DecimalField` | No | Duración externa Main Story. |
| `igdb_payload` | `JSONField` | No | Respuesta original o datos relevantes de IGDB. |
| `franchise` | `ForeignKey` | No | Franquicia manual opcional. |
| `created_at` | `DateTimeField` | Sí | Fecha de importación o creación. |
| `updated_at` | `DateTimeField` | Sí | Última modificación. |

### Reglas

- `igdb_id` debe ser único cuando exista.
- Deben permitirse juegos manuales sin `igdb_id`.
- `slug` debe ser único.
- `igdb_main_story_hours` debe ser positivo.
- Solo se almacenará la estimación **Main Story**.
- No se incluirán estimaciones Main + Extra ni Completionist en el MVP.
- La biblioteca debe cargar desde PostgreSQL, no desde IGDB.

### Ejemplo

```text
Game
title: Yakuza Kiwami 2
igdb_id: 76758
first_release_date: 2017-12-07
igdb_main_story_hours: 18.5
franchise: Yakuza / Like a Dragon
```

---

## 5. LibraryEntry

Representa la relación personal con un videojuego.

Cada `Game` podrá tener como máximo una `LibraryEntry`.

Aquí viven el estado general, las notas personales, el indicador de platino y la duración manual.

### Estados propuestos

```text
playing
paused
dropped
plan_to_play
completed
multiplayer
```

### Campos propuestos

| Campo | Tipo sugerido | Requerido | Descripción |
|---|---|---:|---|
| `game` | `OneToOneField` | Sí | Juego asociado. |
| `status` | `CharField` | No | Estado personal general. |
| `has_platinum` | `BooleanField` | Sí | Indica si el platino está marcado. |
| `main_story_hours_override` | `DecimalField` | No | Corrección manual de la duración. |
| `notes` | `TextField` | No | Notas personales. |
| `created_at` | `DateTimeField` | Sí | Fecha de incorporación. |
| `updated_at` | `DateTimeField` | Sí | Último cambio. |

### Reglas

- Un `Game` no puede tener más de una `LibraryEntry`.
- `status` puede quedar vacío cuando el juego solo está en wishlist.
- `has_platinum` comienza en `False`.
- `main_story_hours_override` debe ser positivo.
- El platino pertenece a la entrada personal completa.
- El platino no depende de `GameAccess`.
- Un juego poseído en PC puede marcarse como candidato a platinar posteriormente en PS5.

### Duración efectiva

La duración utilizada por la interfaz y los análisis será:

```text
main_story_hours_override
        si existe

igdb_main_story_hours
        en caso contrario
```

### Propiedades derivadas sugeridas

```python
effective_main_story_hours
is_owned
is_wishlisted
```

### Ejemplo

```text
LibraryEntry
game: Yakuza Kiwami 2
status: playing
has_platinum: false
main_story_hours_override: 20
```

---

## 6. GameAccess

Representa dónde se posee o se desea adquirir un juego.

Este modelo permite expresar casos como:

```text
Yakuza 0
├── Owned · PC · Steam
└── Wishlist · PlayStation · PS5
```

El juego no se duplica: existen diferentes accesos asociados a la misma `LibraryEntry`.

### Tipos de acceso

```text
owned
wishlist
```

### Familias de plataforma iniciales

```text
playstation
pc
nintendo
xbox
other
```

### Campos propuestos

| Campo | Tipo sugerido | Requerido | Descripción |
|---|---|---:|---|
| `library_entry` | `ForeignKey` | Sí | Entrada personal asociada. |
| `access_type` | `CharField` | Sí | `owned` o `wishlist`. |
| `platform_family` | `CharField` | Sí | Familia principal de plataforma. |
| `platform_name` | `CharField` | No | PS5, PC, Switch, Xbox Series, etc. |
| `store` | `CharField` | No | Steam, Epic, PS Store u otra tienda. |
| `acquired_on` | `DateField` | No | Fecha de adquisición. |
| `notes` | `TextField` | No | Información adicional. |
| `created_at` | `DateTimeField` | Sí | Fecha de registro. |
| `updated_at` | `DateTimeField` | Sí | Último cambio. |

### Reglas

- Un acceso debe pertenecer a una `LibraryEntry`.
- `acquired_on` normalmente se usa con `owned`.
- El MVP no distinguirá compra física, digital o suscripción.
- Un juego puede tener múltiples accesos.
- Debe evitarse duplicar exactamente la misma combinación de:

```text
library_entry
access_type
platform_family
platform_name
store
```

### Métricas derivadas

```text
Posees
    Juegos con al menos un GameAccess de tipo owned.

Wishlist
    Juegos con al menos un GameAccess de tipo wishlist.
```

Un mismo juego puede formar parte de ambos conteos cuando existen accesos diferentes.

---

## 7. Playthrough

Representa cada recorrido individual realizado sobre un juego.

Un juego puede tener varios playthroughs con distintos idiomas, fechas, plataformas y resultados.

### Estados propuestos

```text
playing
paused
completed
dropped
```

### Idiomas iniciales

```text
ja      Japonés
en      Inglés
es      Español
other   Otro
```

Cada playthrough tendrá un solo idioma de texto.

Las voces no se registrarán en el MVP.

### Campos propuestos

| Campo | Tipo sugerido | Requerido | Descripción |
|---|---|---:|---|
| `library_entry` | `ForeignKey` | Sí | Entrada personal asociada. |
| `access` | `ForeignKey` | No | Plataforma o acceso utilizado. |
| `number` | `PositiveIntegerField` | Sí | Número del recorrido. |
| `status` | `CharField` | Sí | Estado del playthrough. |
| `text_language` | `CharField` | Sí | Idioma principal del texto. |
| `started_on` | `DateField` | No | Fecha de inicio. |
| `finished_on` | `DateField` | No | Fecha de término. |
| `progress_note` | `CharField` | No | Progreso manual libre. |
| `hours_played` | `DecimalField` | No | Duración real opcional. |
| `notes` | `TextField` | No | Contexto o impresiones. |
| `created_at` | `DateTimeField` | Sí | Fecha de registro. |
| `updated_at` | `DateTimeField` | Sí | Último cambio. |

### Reglas

- `number` debe ser único dentro de la misma `LibraryEntry`.
- `number` debe comenzar en `1`.
- `finished_on` no puede ser anterior a `started_on`.
- `hours_played` debe ser positivo.
- El `GameAccess` seleccionado debe pertenecer a la misma `LibraryEntry`.
- Un playthrough completado puede tener fecha de término.
- El progreso es opcional y manual.
- No habrá porcentaje universal ni estimación automática de finalización.

### Ejemplos de progreso válido

```text
Capítulo 7
Acto 2
63%
Final de la historia
Historia principal terminada
```

### Ejemplo de historial

```text
Yakuza 0
├── Playthrough 1 · English · Completed
└── Playthrough 2 · Español · Completed
```

---

## 8. Restricciones y validaciones

### Restricciones de base de datos

Se consideran necesarias:

- `Game.igdb_id` único cuando no sea nulo.
- `Game.slug` único.
- `Franchise.name` único.
- `Franchise.slug` único.
- Relación uno a uno entre `Game` y `LibraryEntry`.
- Combinación única de `library_entry` y `number` en `Playthrough`.
- Restricción de duración positiva para:
  - `igdb_main_story_hours`.
  - `main_story_hours_override`.
  - `hours_played`.
- Restricción de `number >= 1`.
- Restricción para evitar accesos duplicados exactos.

### Validaciones de modelo

Algunas reglas requieren `clean()` o validación de formulario:

- `finished_on >= started_on`.
- El `access` de un playthrough pertenece a la misma `LibraryEntry`.
- `acquired_on` tiene sentido para accesos `owned`.
- Los estados y fechas de un playthrough son coherentes.
- Una entrada sin estado debe tener al menos un acceso de wishlist.

---

## 9. Relaciones Django propuestas

```python
Franchise
    games = related_name="games"

Game
    library_entry = related_name="game"
    franchise = related_name="games"

LibraryEntry
    accesses = related_name="accesses"
    playthroughs = related_name="playthroughs"

GameAccess
    playthroughs = related_name="playthroughs"

Playthrough
    library_entry = related_name="playthroughs"
    access = related_name="playthroughs"
```

Los nombres exactos deberán evitar colisiones y mantenerse consistentes con el estilo final de `models.py`.

---

## 10. Flujos principales

### Importar un juego desde IGDB

```text
Buscar en IGDB
        ↓
Seleccionar resultado
        ↓
Guardar Game localmente
        ↓
Crear LibraryEntry
        ↓
Agregar GameAccess
```

### Crear una entrada manual

```text
Crear Game sin igdb_id
        ↓
Crear LibraryEntry
        ↓
Agregar acceso owned o wishlist
```

### Registrar un playthrough

```text
Abrir LibraryEntry
        ↓
Seleccionar GameAccess opcional
        ↓
Crear Playthrough
        ↓
Indicar idioma de texto
        ↓
Actualizar progreso y estado manualmente
```

---

## 11. Métricas futuras

### Biblioteca

- Total de juegos registrados.
- Total de juegos poseídos.
- Total de juegos en wishlist.
- Total por estado.
- Completados frente a juegos poseídos.
- Completados frente a biblioteca total.
- Juegos multiplayer.
- Juegos con platino.
- Candidatos a platinar.

### Accesos

- Juegos por plataforma.
- Juegos por tienda.
- Juegos poseídos en más de una plataforma.
- Juegos poseídos y también deseados en otra plataforma.

### Playthroughs

- Total de playthroughs.
- Playthroughs completados.
- Juegos rejugados.
- Idioma de texto por playthrough.
- Tiempo real jugado.
- Diferencia entre duración estimada y duración real.

### Franquicias

- Juegos completados por franquicia.
- Progreso de cada saga.
- Juegos pendientes por franquicia.
- Franquicias enfocadas en multiplayer.

---

## 12. Integración futura con Hibi Log

Hibi Log podrá relacionar sesiones de actividad con:

- Una `LibraryEntry`.
- Un `Playthrough`.
- Un `GameAccess` cuando sea necesario.

Ejemplo:

```text
ActivitySession
game_library_entry: Yakuza Kiwami 2
playthrough: Playthrough 1
duration_minutes: 95
progress_from: Chapter 6
progress_to: Chapter 7
notes: Sesión de historia principal en japonés
```

La relación exacta se definirá dentro del diseño de Hibi Log, pero Game Kiroku debe exponer identificadores estables para permitirla.

---

## 13. Decisiones fuera del MVP

No se incluirán inicialmente:

- Diferentes variantes de tiempo de finalización.
- Seguimiento de voces o doblaje.
- Sistema universal de porcentaje de progreso.
- Estimación automática de fecha de finalización.
- Trofeos individuales.
- Logros de Steam.
- Distinción entre copia física, digital o suscripción.
- Múltiples usuarios o bibliotecas públicas.
- Sincronización permanente con IGDB.
- Duplicación del juego por plataforma.
- Relaciones automáticas de franquicia importadas desde IGDB.

Estas funciones podrán evaluarse después de validar el MVP.

---

## 14. Orden de implementación

```text
1. Definir TextChoices
2. Crear Franchise
3. Crear Game
4. Crear LibraryEntry
5. Crear GameAccess
6. Crear Playthrough
7. Agregar constraints
8. Agregar clean() y propiedades
9. Registrar modelos en admin
10. Crear primera migración
11. Probar migración en SQLite
12. Aplicar migración en Supabase
13. Crear CRUD local
14. Integrar IGDB
```

---

## 15. Estado de aprobación

```text
Documento: game-kiroku-data-model.md
Módulo: Game Kiroku
Etapa: Diseño previo a migraciones
Estado: Pendiente de revisión final
```

No ejecutar todavía:

```bash
python manage.py makemigrations games
python manage.py migrate
```

La primera migración debe crearse únicamente después de revisar y aprobar los campos, relaciones, restricciones y nombres definitivos.
