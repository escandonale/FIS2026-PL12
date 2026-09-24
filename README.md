# Proyecto Fundamentos 2026
Proyecto para la asignatura "Fundamentos de la Ingeniería de Software" de Mateo Alonso, Alejandro Escandón y Nicolás de la Vega

Acceso al KanBan: [...]

Acceso al modelo de datos: https://dbdiagram.io/d/modelo-SisRec-68e3f5f2d2b621e422831408


IMPORTAR Y EXPORTAR ENVIROMENT\
importar enviroment: pip install -r requirements.txt\
exportar enviroment: pip freeze > requirements.txt\
Librerías incluidas en el enviroment:

[...]


ESTRUCTURA DEL PROYECTO


FIS2026-PL12\
├── resources/\
│   ├── schema.sql     Esquema de la base de datos (se borra y recrea en cada arranque)\
│   └── data.sql       Carga inicial de datos\
├── src/               Código fuente\
│   ├── main.py        Punto de entrada y configuración del logging (mensajes)\
│   ├── config.py      Rutas de la base de datos y scripts SQL\
│   ├── employees/     Capa de empleados (modelo y vista)\
│   └── util/          Acceso a datos, validaciones y excepciones\
├── test/              Tests unitarios (unittest / pytest)\
├── ideas HUs          Ideas para las historias de usuario\
└── README.md          README para el proyecto de la asignatura\