# Infraestructura Mobile QA — VM Android en GCP

> **Última actualización:** 2026-06-17  
> **Estado general:** ⏳ Emulador verificado — pendiente APKs para crear imagen v4

---

## Arquitectura General

El agente QA ejecuta tests mobile en una VM efímera de GCP que levanta un emulador Android,
corre Appium, y se apaga sola. El ciclo completo toma ~4 minutos desde imagen preconfigurada.

```
Trigger (Jira/Slack)
       ↓
Crear VM desde imagen android-qa-base-vN  (~30 seg)
       ↓
Startup script: boot emulador + wait ADB + instalar APK  (~2 min)
       ↓
Correr tests Appium  (variable)
       ↓
Subir resultados/screenshots a GCS
       ↓
Shutdown VM  (costo $0 en reposo)
```

---

## Recursos GCP

| Recurso | Valor |
|---|---|
| Proyecto | `procontacto-claude` |
| Zona | `us-central1-a` |
| VM de setup | `android-qa-setup` |
| Imagen activa | `android-qa-base-v3` |
| Imagen objetivo | `android-qa-base-v4` ⏳ pendiente |
| Bucket GCS | `gs://procontacto-claude-qa/` |
| Machine type | `n2-standard-4` |
| CPU platform | `Intel Cascade Lake` (requerido para nested virtualization / KVM) |

---

## Scripts en GCS

| Script | Ruta | Propósito |
|---|---|---|
| `setup-emulator.sh` | `gs://procontacto-claude-qa/scripts/setup-emulator.sh` | Inicia emulador, toma screenshot, sube a GCS (sin shutdown — para setup) |
| `startup-v7-image-based.sh` | `gs://procontacto-claude-qa/scripts/startup-v7-image-based.sh` | Producción: boot + screenshot + shutdown |
| `appium-install-v2.sh` | `gs://procontacto-claude-qa/scripts/appium-install-v2.sh` | Instala Appium en la VM |

---

## Imagen `android-qa-base-v3` — Contenido

**Incluye:**
- Android SDK completo
- AVD `test_avd` — Android 34, `google_apis_playstore`, `x86_64`
- Appium
- ADB (`/android/platform-tools/adb`)
- ADB key en `/root/.android/adbkey` (auto-autoriza el emulador sin diálogos)
- Nested virtualization habilitada

**NO incluye (APKs — pendiente):**
- `app_offline.apk` (app custom `appoffline.com.mx`)
- `salesforce.apk` (Salesforce Mobile)

---

## Patrón Correcto para Iniciar el Emulador

> ⚠️ Bug conocido y corregido: `nohup HOME=/root ...` no funciona — nohup trata `HOME=/root` como el comando.  
> Fix: usar variables de entorno inline sin nohup.

```bash
# ✅ Correcto
HOME=/root ANDROID_HOME=/android $ADB kill-server 2>/dev/null || true
HOME=/root ANDROID_HOME=/android $ADB start-server
sleep 3
HOME=/root ANDROID_HOME=/android $EMU -avd test_avd \
  -no-window -no-audio -gpu swiftshader_indirect \
  -no-boot-anim -no-metrics -no-snapshot-save \
  > /tmp/emu.log 2>&1 &

# ❌ Incorrecto (falla silenciosamente)
nohup HOME=/root ANDROID_HOME=/android $EMU ...
```

---

## Estado de la VM

```bash
# Ver estado actual
gcloud compute instances list \
  --project=procontacto-claude \
  --filter="name=android-qa-setup" \
  --format="table(name,status,zone)"

# Levantar para setup
gcloud compute instances start android-qa-setup --zone=us-central1-a

# SSH
gcloud compute ssh android-qa-setup --zone=us-central1-a
```

**Estado al 2026-06-03:** `TERMINATED` (apagada, sin costo)

---

## Hitos Completados ✅

- [x] Imagen `android-qa-base-v3` creada con SDK + AVD + Appium
- [x] Nested virtualization habilitada (KVM acceleration)
- [x] Ciclo rápido verificado: imagen → emulador → screenshot → shutdown en **~4 min**
- [x] Bug de `nohup` encontrado y corregido
- [x] Emulador Android 14 confirmado funcionando
- [x] Screenshot de prueba exitosa: `gs://procontacto-claude-qa/mobile-test/boot_test_20260517_042229.png`
- [x] ADB detecta `sys.boot_completed=1` en ~50 segundos desde inicio del emulador

---

## Próximos Pasos para `android-qa-base-v4`

### 1. Obtener APKs ⏳ — bloqueante
- `app_offline.apk` — app custom de `appoffline.com.mx` → **Axel lo provee**
- `salesforce.apk` — Salesforce Mobile → **Axel confirma: APK directo o Play Store**

### 2. Subir APKs a GCS
```bash
gsutil cp app_offline.apk gs://procontacto-claude-qa/apks/
gsutil cp salesforce.apk gs://procontacto-claude-qa/apks/
```

### 3. Instalar APKs en el emulador activo
```bash
# Levantar VM y SSH
gcloud compute instances start android-qa-setup --zone=us-central1-a
gcloud compute ssh android-qa-setup --zone=us-central1-a

# Descargar e instalar APKs
sudo gsutil cp gs://procontacto-claude-qa/apks/app_offline.apk /tmp/
sudo HOME=/root ANDROID_HOME=/android /android/platform-tools/adb install /tmp/app_offline.apk

sudo gsutil cp gs://procontacto-claude-qa/apks/salesforce.apk /tmp/
sudo HOME=/root ANDROID_HOME=/android /android/platform-tools/adb install /tmp/salesforce.apk
```

### 4. Guardar snapshot del AVD
```bash
HOME=/root ANDROID_HOME=/android /android/platform-tools/adb emu avd snapshot save qa_with_apps
```

### 5. Crear imagen `android-qa-base-v4`
```bash
gcloud compute instances stop android-qa-setup --zone=us-central1-a

gcloud compute images create android-qa-base-v4 \
  --source-disk=android-qa-setup \
  --source-disk-zone=us-central1-a \
  --family=android-qa
```

### 6. Escribir test Appium
- Path en VM: `/opt/tests/salesforce_login.js`
- Objetivo: login con usuario/password en Salesforce Mobile
- Ver también: Permission Set "QA MFA Waiver" en Salesforce ⏳ pendiente confirmar con equipo

---

## Notas de Arquitectura

**¿Por qué sin snapshot en el startup script de producción?**  
Se usa `-no-snapshot-save` para evitar corrupción si el emulador es matado abruptamente.
El snapshot se guarda UNA sola vez durante el setup de la imagen, antes de crearla.

**¿Por qué no hay APKs en la imagen v3?**  
Se separó el setup del SDK/AVD de la instalación de apps para tener una base limpia
y poder recrear la imagen v4 fácilmente cuando cambien los APKs.

**Credenciales MFA en Salesforce Mobile**  
Para que el agente pueda loguearse sin intervención humana, se necesita
un Permission Set que exima al usuario QA del MFA. Consultar con el equipo de SF.

---

## Bloqueantes Pendientes

| Item | Responsable | Estado |
|---|---|---|
| APK de App Offline (`appoffline.com.mx`) | Axel | ⏳ Pendiente |
| APK de Salesforce Mobile | Axel | ⏳ Pendiente (APK o Play Store?) |
| Permission Set "QA MFA Waiver" en Salesforce | Axel + equipo SF | ⏳ Pendiente confirmar |
