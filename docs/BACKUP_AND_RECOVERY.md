# Manual de Políticas de Backup y Procedimientos de Recuperación

**Nexo Analytics · Commercial & Lead Intelligence Suite**

---

## 📌 1. Política de Respaldo de Datos

El sistema implementa una política de **respaldos automáticos antes de mutación (Pre-Write Snapshots)** y herramientas CLI para respaldos manuales.

### Tipos de Datos Respaldados
1. **Base de Datos de Leads CRM (`Leeds orden.xlsx`)**: Contiene prospectos, teléfonos, asignaciones a closers y estado de interacciones.
2. **Base de Datos Comercial (`Comercial.xlsx`)**: Contiene pauta publicitaria, campañas de Meta Ads, presupuestos e historial de cotizaciones.
3. **Estado de Sincronización WhatsApp (`whatsapp_sync_state.json`)**: Registro de deduplicación de mensajes procesados.
4. **Credenciales de Sesión WhatsApp (`whatsapp_bridge/auth_info_baileys/`)**: Claves criptográficas de la vinculación activa por código QR.

---

## ⚙️ 2. Backups Automáticos

Cada vez que el motor de sincronización de WhatsApp (`whatsapp_service.py`) o el usuario realiza una modificación masiva o persistencia en el archivo Excel de Leads:
- Se genera automáticamente una copia con timestamp en la carpeta `backups/`.
- Formato del nombre: `Leeds_orden_YYYYMMDD_HHMMSS_<tag>.xlsx`.
- **Rotación automática**: El sistema conserva por defecto las últimas 20 copias históricas, eliminando las más antiguas para optimizar el almacenamiento.

---

## 🛠️ 3. Comandos CLI de Administración

Puede administrar los backups directamente desde la línea de comandos usando Python:

### 1. Crear un backup manual inmediato
```bash
python scripts/backup_manager.py backup --tag antes_de_actualizacion
```

### 2. Listar todos los backups existentes
```bash
python scripts/backup_manager.py list
```

### 3. Respaldar la sesión activa de WhatsApp
```bash
python scripts/backup_manager.py backup-session
```
*Genera un archivo `.zip` con marca de tiempo en `backups/whatsapp_sessions/`.*

### 4. Restaurar una copia de seguridad
```bash
python scripts/backup_manager.py restore backups/Leeds_orden_20260829_105000_auto.xlsx "Leeds orden.xlsx"
```
*(Nota: El sistema automáticamente creará una copia de seguridad de protección `pre_restore_safety` del archivo actual antes de sobreescribir).*

---

## 🚨 4. Procedimientos de Recuperación ante Incidentes (Disaster Recovery)

### Caso A: Corrupción del archivo Excel o Sobreescritura Accidental
1. Cierre el Dashboard de Streamlit o la GUI de escritorio si están abiertos.
2. Liste los backups disponibles:
   ```bash
   python scripts/backup_manager.py list
   ```
3. Identifique el último backup íntegro previo al incidente.
4. Ejecute el comando de restauración:
   ```bash
   python scripts/backup_manager.py restore "backups/<nombre_del_backup>.xlsx" "Leeds orden.xlsx"
   ```
5. Inicie nuevamente la aplicación (`iniciar_dashboard.bat` o `iniciar.bat`) y verifique la integridad en la pestaña **Calidad de Datos**.

---

### Caso B: Desconexión o Falla de la Sesión de WhatsApp Baileys
Si el puente de WhatsApp pierde la sincronización o se reporta error de autenticación:
1. **Para reconectar desde cero**:
   - Detenga el servidor de WhatsApp (`Ctrl+C` en la terminal del bridge).
   - Elimine la carpeta de sesión temporal:
     ```powershell
     Remove-Item -Recurse -Force whatsapp_bridge\auth_info_baileys
     ```
   - Inicie el puente nuevamente (`node whatsapp_bridge/server.js`) y escanee el nuevo código QR generado en la consola o dashboard.
2. **Para restaurar una sesión previamente respaldada**:
   - Descomprima el archivo zip más reciente ubicado en `backups/whatsapp_sessions/` dentro del directorio `whatsapp_bridge/auth_info_baileys/`.
   - Reinicie el servicio Node.js.

---

### Caso C: Estado de Sincronización Inconsistente (`whatsapp_sync_state.json`)
Si desea re-procesar todos los mensajes entrantes de WhatsApp desde cero:
1. Haga una copia del archivo:
   ```powershell
   Copy-Item whatsapp_sync_state.json backups\whatsapp_sync_state_backup.json
   ```
2. Resetee el archivo de sincronización creando un JSON vacío:
   ```json
   {
     "processed_message_ids": [],
     "last_sync_timestamp": null
   }
   ```
3. Al reiniciar la app, el motor re-analizará los mensajes pendientes de `whatsapp_inbox/` o del bridge.
