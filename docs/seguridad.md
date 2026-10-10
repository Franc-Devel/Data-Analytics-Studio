# Revisión de publicación / Publication review

## Español

Revisión realizada el 10 de octubre de 2026 sobre una selección explícita de archivos
del snapshot de origen `1c6b02c5767e139c77ed581713706cfe99b96a3d`.
La copia pública inicia un historial independiente; no importa commits ni metadatos
personales del historial privado.

- Conservados: módulos Python, pruebas, dependencias y lanzador, revisados como texto.
- Excluidos: todos los `__pycache__` y binarios compilados, que pueden contener rutas
  y metadatos locales.
- Excluido: `todo_el_contenido_diplomatura.md`. Material académico ajeno al código
  de la aplicación; no se redistribuye ni se presume permiso sobre su contenido.
- Excluido: CSV original, cuya procedencia sintética no se da por comprobada.
  Se reemplaza por un generador determinista sin personas, contactos ni identificadores.
- README reemplazado para corregir contenido mal codificado y describir el alcance real.
- No se encontraron credenciales, tokens, claves privadas, conexiones privadas ni
  llamadas de red en el código seleccionado. La terminal interna usa comandos
  predefinidos y no ejecuta código o comandos del sistema.
- La aplicación lee archivos locales y exporta Excel en la ruta elegida. No implementa
  autenticación, cifrado de archivos, anonimización ni almacenamiento remoto.
- `.gitignore` excluye entornos, secretos comunes, datos locales y exportaciones.
  Es una prevención, no una garantía: revisar todo archivo antes de agregarlo a Git.

Los archivos excluidos no se han considerado seguros ni se han importado.
La revisión se aplica a todos los archivos que integran esta entrega y a cada
snapshot del historial nuevo; no certifica el repositorio privado completo.
Las dependencias requieren su propia revisión ante cambios de versión.

## English

The public copy uses an explicit source-file allowlist and a fresh history.
Compiled caches, the original CSV and academic course material are excluded.
Examples are generated deterministically from scratch with no personal records.
No credentials, private endpoints or network calls were found in the selected code.
The embedded terminal accepts predefined commands only.

Files stay local; Excel exports are written to the user-selected path. There is no
authentication, file encryption or anonymization. Ignore rules are preventive;
review each future addition. This review covers the public deliverable and its new
history, not the entire private repository or a dependency vulnerability audit.
