# Proyecto Fundamentos 2026
Proyecto para la asignatura "Fundamentos de la Ingeniería de Software" de Mateo Alonso, Alejandro Escandón y Nicolás de la Vega

Acceso al KanBan: https://in2test.lsi.uniovi.es/redkanban/

Acceso al modelo de datos: https://dbdiagram.io/d/modelo-SisRec-68e3f5f2d2b621e422831408


IMPORTAR Y EXPORTAR ENVIROMENT\
importar enviroment: pip install -r requirements.txt\
exportar enviroment: pip freeze > requirements.txt\
La aplicación utiliza `prettytable` para presentar los datos en tablas.


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
Cuando no existe `centro_deportivo.db`, se carga automáticamente [data.sql](./data.sql)
con diez actividades de ejemplo, perfiles e inscripciones. Para crear una base
vacía, comenta la llamada a `database.executeScript(DATA)` en `main.py`.
Los datos de ejemplo generan ocupación completa en la actividad 1 y entre el
50 % y el 90 % en las restantes; se insertan primero las inscripciones de socios
y hay el doble de perfiles e inscripciones de no socios.

Para gestionar actividades, primero se crea la actividad indicando categoría,
nivel, días, horario y plazas. La asignación de una instalación se realiza
después desde la opción correspondiente del menú; solo se ofrecen instalaciones
compatibles con la categoría de la actividad.

Una instalación no puede tener dos actividades simultáneas el mismo día. Los
horarios contiguos (por ejemplo, 18:00-19:00 y 19:00-20:00) sí están permitidos.
Al iniciar la aplicación se informa de los solapamientos que ya existan en la
base de datos y se bloquean las altas hasta corregirlos reasignando una de las
actividades.

El menú permite asignar instalaciones (opción 3), gestionar globalmente los
plazos globales de inscripción para socios y no socios (opción 4), inscribir
personas (opción 5), consultar ocupación e inscripciones (opción 6) y cancelar
una inscripción (opción 7). La opción 11 muestra la ocupación semanal de un
espacio para la franja seleccionada (mañana, mediodía o tarde), con una cuadrícula
de actividades y disponibilidad, porcentajes por hora y día, y los picos de
ocupación. El registro de asistencia (opción 10) se guarda por sesión y permite
corregir un pase de lista. La opción 12 compara plazas planificadas y asistencia
real por semana y espacio; permite revisar semanas anteriores y ver una gráfica
de evolución por actividad. La semana actual es la predeterminada y se puede
retroceder con la opción `A`. La asistencia real solo se conserva desde que se
empieza a guardar cada pase de lista; los registros anteriores no se pueden
reconstruir automáticamente. Los plazos se guardan en la oferta y se replican
en las actividades para compatibilidad con los datos anteriores; cada cierre debe
ser anterior al inicio de todas las actividades. El gestor puede programar
fechas, abrir ahora o cerrar ahora
el plazo de cada grupo; la programación y los cambios inmediatos se aplican
simultáneamente a todas las actividades. Las fechas deben usar `AAAA-MM-DD`,
ser fechas válidas, comenzar hoy o después y cerrar después de la apertura. Los
socios deben existir previamente en `Socios`; los no socios proporcionan sus
datos al inscribirse.

Las cancelaciones se permiten hasta 15 días antes del primer día del mes de
inicio de la actividad. Al cancelar una plaza confirmada, se confirma la
inscripción más antigua de la lista de espera; si no hay lista de espera, se
libera la plaza. Cada inscripción se guarda en `inscripcion`.
`available_places` representa la capacidad total y `occupied_places` no puede
ser negativo ni superarla.

ESTADO DE LAS HISTORIAS DE USUARIO

- Como gestor de actividades quiero añadir una nueva actividad a la oferta actual
  para que se pueda inscribir posteriormente a los usuarios. Implementado desde el
  menú de alta de actividades.
- Como usuario quiero registrarme como socio en el programa para tener prioridad en
  las actividades. Implementado con el alta de socios y comprobación de DNI y
  número de socio únicos.
- Como usuario socio ya registrado quiero poder inscribirme en una actividad
  deportiva para participar en ella teniendo prioridad. Implementado en la
  inscripción de socios con un periodo de inscripción anterior al de no socios.
- Como usuario quiero cancelar mi inscripción en una actividad deportiva para dejar
  mi plaza libre y anular el pago. La cancelación y promoción de la lista de espera
  están implementadas; el sistema de pagos y su anulación todavía no.
- Como gestor de actividades quiero abrir el plazo de inscripción de una
  actividad para que los usuarios se inscriban dentro de unos márgenes. Implementado
  con la configuración del calendario de inscripción por grupos.
- Como gestor de actividades quiero visualizar el listado de asistentes y el estado
  de una actividad para realizar el control de plazas, acceso y ocupación.
  Implementado en la vista de control de plazas.
- Como gestor de actividades quiero asignar la actividad a un espacio para su
  posterior inscripción. Implementado con la asignación de instalaciones compatibles.
- Como responsable de actividades quiero consultar la ocupación por espacio y
  franja horaria para identificar las franjas más ocupadas. Implementado en el
  informe semanal de ocupación.
- Como gestor de actividades quiero rellenar un registro de asistencia para poder
  generar información. Se guarda la asistencia de cada sesión en la base de datos.
- Como gestor de actividades quiero comparar la ocupación planificada con la real
  para detectar desajustes en el uso de las instalaciones. Implementado con
  comparación semanal y gráfica de evolución por actividad.

La funcionalidad de registro de personas queda cubierta para ambos perfiles del
sistema. En ambos registros se solicita el género como `m`, `f` o `n`; el formulario
muestra la equivalencia de cada opción y el sistema no acepta otros valores:
- socio: nombre, apellidos, género, DNI, número de socio y dirección;
- no socio: género, nombre, apellidos, fecha de nacimiento, dirección, DNI, correo
  y fecha de alta automáticas.
El DNI no puede estar registrado simultáneamente en ambos perfiles. Los no socios
también pueden inscribirse sin completar previamente el alta de perfil; en ese caso
se recogen sus datos en el momento de la inscripción.

El pago es una funcionalidad pendiente: el proyecto todavía no define si será
mensual o único, ni importe, método de pago o estados de devolución.
