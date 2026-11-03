# Proyecto Fundamentos 2026
Proyecto para la asignatura "Fundamentos de la Ingeniería de Software" de Mateo Alonso, Alejandro Escandón y Nicolás de la Vega

Acceso al KanBan: https://in2test.lsi.uniovi.es/redkanban/

Acceso al modelo de datos: https://dbdiagram.io/d/modelo-SisRec-68e3f5f2d2b621e422831408


IMPORTAR Y EXPORTAR ENVIROMENT\
importar enviroment: pip install -r requirements.txt\
exportar enviroment: pip freeze > requirements.txt\
Librerías incluidas en el enviroment:

[...]


ESTRUCTURA DEL PROYECTO


FIS2026-PL12\
├── main.py            Punto de entrada de la aplicación\
├── src/               Código fuente y lógica de negocio\
│   ├── activities.py  Gestión de actividades e instalaciones\
│   ├── actividades/   Inscripciones y cancelaciones\
│   ├── resources/     Esquema y restricciones SQLite\
│   └── util/          Acceso a datos y excepciones\
├── tests/             Tests unitarios (unittest)\
├── sample/            Material heredado y ejemplos\
├── ideas HUs          Ideas para las historias de usuario\
└── README.md          README para el proyecto de la asignatura\


EJECUCIÓN DE LA APLICACIÓN

Desde la carpeta raíz del proyecto, ejecutar `python main.py`.
La aplicación aplica el esquema y migraciones compatibles sin borrar las
actividades e inscripciones existentes y muestra el menú de consola.

Para gestionar actividades, primero se crea la actividad indicando categoría,
nivel, días, horario y plazas. La asignación de una instalación se realiza
después desde la opción correspondiente del menú; solo se ofrecen instalaciones
compatibles con la categoría de la actividad.

Una instalación no puede tener dos actividades simultáneas el mismo día. Los
horarios contiguos (por ejemplo, 18:00-19:00 y 19:00-20:00) sí están permitidos.
Al iniciar la aplicación se informa de los solapamientos que ya existan en la
base de datos y se bloquean las altas hasta corregirlos reasignando una de las
actividades.

El menú permite asignar instalaciones (opción 3), configurar los plazos de
inscripción para socios y no socios (opción 4), inscribir personas (opción 5),
consultar ocupación e inscripciones (opción 6) y cancelar una inscripción
(opción 7). Los plazos se guardan en la actividad y deben terminar antes de
su fecha de inicio. Cada tipo de persona solo puede inscribirse durante su
periodo. Los socios deben existir previamente en `Socios`; los no socios
proporcionan sus datos al inscribirse.

Las cancelaciones se permiten hasta 15 días antes del primer día del mes de
inicio de la actividad. Al cancelar una plaza confirmada, se confirma la
inscripción más antigua de la lista de espera; si no hay lista de espera, se
libera la plaza. Cada inscripción se guarda en `inscripcion`.
`available_places` representa la capacidad total y `occupied_places` no puede
ser negativo ni superarla.
