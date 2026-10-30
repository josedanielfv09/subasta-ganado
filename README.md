# Sistema de Control de Operaciones de Subasta de Ganado

Proyecto de Ingeniería de Software. Sistema en Python para gestionar lotes, animales, jornadas, compradores, pujas por kilo y facturación en subastas de ganado.

Tiene dos versiones que comparten las mismas 24 clases y los 50 requerimientos:

- **Versión de escritorio** (`Sistema_Subasta_Ganado.py`): interfaz Tkinter.
- **Versión web** (`app.py` + `logica.py` + `templates/`): interfaz en el navegador con Flask, publicada en Render.

## Tecnologías
- Python 3
- Tkinter y tkcalendar (versión de escritorio)
- Flask y Gunicorn (versión web)

## Ejecución

Versión de escritorio:

    pip install tkcalendar
    python Sistema_Subasta_Ganado.py

Versión web (local):

    pip install -r requirements.txt
    python app.py

Luego abrir http://127.0.0.1:5000

Versión web en producción (Render):

    Build Command: pip install -r requirements.txt
    Start Command: gunicorn app:app
    Variables de entorno: SECRET_KEY, ADMIN_USUARIO, ADMIN_CONTRASENA

## Acceso y roles (versión web)
Al abrir la página por primera vez se crea la cuenta del administrador (o se define con las variables de entorno `ADMIN_USUARIO` y `ADMIN_CONTRASENA`). El administrador crea los demás usuarios con uno de tres roles:

- **Administrador:** todo, incluidos usuarios, respaldos y cierre de jornadas.
- **Registrador:** registra y edita lotes, animales, subastas, ventas y abonos.
- **Consulta:** solo consulta reportes, facturas y ganancias.

Las facturas y los reportes se descargan en PDF y Excel, y desde la sección Respaldo se crean y restauran copias de seguridad.

## Requerimientos principales
- Registro de lotes de 10 a 30 animales
- Registro de animales con tipo, raza, peso e ICA único
- Jornadas de subasta (lunes, miércoles y sábado)
- Subasta en vivo con pujas por kilo
- Cálculo de ganancias por lote y generales
- Facturación y reportes

## Autores
- Isaac Arteaga
- Albeiro Bedoya
- José Fernández
- Martín López
- Jesús Ruiz
