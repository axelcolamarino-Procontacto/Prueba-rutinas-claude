# Infraestructura Mobile QA — VM Android en GCP

> **Última actualización:** 2026-06-03
> **Estado general:** ✅ Imagen `android-qa-base-v5` creada con Salesforce + CG Cloud preinstalados

---

## Arquitectura General

El agente QA ejecuta tests mobile en una VM efímera de GCP que levanta un emulador Android,
corre Appium, y se apaga sola. El ciclo completo toma ~4 minutos desde imagen preconfigurada.

```
Trigger (Jira/Slack)
       ↓
Crear VM desde imagen android-qa-base-vN  (~30 seg)
       ↓
Startup script: boot emulador + wait ADB + (apps ya preinstaladas)  (~2 min)
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
| **Imagen activa (única)** | **`android-qa-base-v5`** (con apps) — `v4` y `v3` borradas |
| Bucket GCS | `gs://procontacto-claude-qa/` |
| Machine type | `n2-standard-4` |
| CPU platform | `Intel Cascade Lake` (requerido para nested virtualization / KVM) |
| Nested virtualization | habilitada (`--enable-nested-virtualization`) |

---

## Acceso a GCP (importante)

- **Auth gcloud:** `gcloud auth login` (flujo navegador / loopback localhost) como `axel.colamarino@procontacto.com.mx`.
  - ⚠️ NO usar `--no-launch-browser`: en el entorno del agente el stdin se rompe (`lost sys.stdin`) y no se puede pegar el código. El login normal con navegador sí funciona.
- **SSH:** usar SSH **directo** (la VM tiene IP externa), NO `--tunnel-through-iap`.
  - El usuario no tiene rol `IAP-secured Tunnel User` → IAP da error `4033: not authorized`.
  - `gcloud compute ssh android-qa-setup --zone=us-central1-a`
- **GCS:** usar `gcloud storage` (NO `gsutil` — falla con `python3.13: command not found` en este SDK).

---

## Scripts en GCS

| Script | Ruta | Propósito |
|---|---|---|
| `setup-emulator.sh` | `gs://procontacto-claude-qa/scripts/setup-emulator.sh` | Inicia emulador, toma screenshot, sube a GCS (sin shutdown — para setup) |
| `startup-v7-image-based.sh` | `gs://procontacto-claude-qa/scripts/startup-v7-image-based.sh` | **Producción**: boot + screenshot + shutdown. Usa `gcloud storage` (fix de `gsutil`). Apps v5 ya preinstaladas. |
| `appium-install-v2.sh` | `gs://procontacto-claude-qa/scripts/appium-install-v2.sh` | Instala Appium en la VM |

---

## Imagen `android-qa-base-v5` — Contenido

**Incluye:**
- Android SDK completo
- AVD `test_avd` — Android 34, `google_apis_playstore`, ABI list `x86_64,arm64-v8a`
- Appium
- ADB (`/android/platform-tools/adb`)
- ADB key en `/root/.android/adbkey` (auto-autoriza el emulador sin diálogos)
- Nested virtualization habilitada
- **Snapshot `default_boot`** del AVD con los apps ya instalados (~68M)
- **Apps preinstaladas:**
  - `com.salesforce.chatter` (Salesforce) — versión **260.050.0**, ABI `x86_64`, launcher `.Chatter`
  - `com.salesforce.industries.offlineapp` (CG Cloud) — versión **260.0006.00**, ABI `arm64-v8a`, launcher `.MainActivity`

---

## Apps Salesforce — Detalle de instalación

| App | Package | Versión | ABI instalada | Launcher |
|---|---|---|---|---|
| Salesforce | `com.salesforce.chatter` | 260.050.0 | x86_64 | `.Chatter` |
| CG Cloud | `com.salesforce.industries.offlineapp` | 260.0006.00 | arm64-v8a | `.MainActivity` |

**Fuente de los APKs:**
- Salesforce: `salesforce1.apk` (APK universal — trae libs x86_64, x86, arm64-v8a, armeabi-v7a). Instala nativo. → `gs://procontacto-claude-qa/apks/salesforce1.apk`
- CG Cloud: del `.xapk` de APKPure (split bundle). ⚠️ El xapk de APKPure trae **solo `config.armeabi_v7a`** (ARM 32-bit), que **NO instala** en el emulador x86_64 (`INSTALL_FAILED_NO_MATCHING_ABIS`, el abilist no incluye armeabi-v7a). La instalación que quedó usa el split **`arm64-v8a`** (de una fuente previa), que SÍ funciona por la traducción ARM64 del emulador.

> 🔑 **Regla ABI:** el emulador soporta `x86_64,arm64-v8a`. Para apps split, instalar el split **`arm64-v8a`** o `x86_64`, NUNCA `armeabi-v7a`.

**Comando de instalación (referencia):**
```bash
ADB="sudo HOME=/root ANDROID_HOME=/android /android/platform-tools/adb"
# Salesforce (universal)
$ADB install -r salesforce1.apk
# CG Cloud (split — base + arm64_v8a + dpi + idiomas)
$ADB install-multiple -r base.apk config.arm64_v8a.apk config.mdpi.apk config.es.apk config.en.apk
```

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
gcloud compute instances list --project=procontacto-claude \
  --filter="name=android-qa-setup" --format="table(name,status,zone)"

# Levantar para setup
gcloud compute instances start android-qa-setup --zone=us-central1-a

# SSH directo (NO IAP)
gcloud compute ssh android-qa-setup --zone=us-central1-a
```

**Estado al 2026-06-03:** `android-qa-setup` apagada tras crear v5. VM de prueba `android-qa-v5-test` se borra tras verificar.

---

## Crear VM desde imagen v5 (referencia)

```bash
gcloud compute instances create android-qa-<nombre> \
  --zone=us-central1-a \
  --image=android-qa-base-v5 \
  --machine-type=n2-standard-4 \
  --min-cpu-platform="Intel Cascade Lake" \
  --enable-nested-virtualization \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --metadata=startup-script-url=gs://procontacto-claude-qa/scripts/setup-emulator.sh
```

---

## Hitos Completados ✅

- [x] Imagen `android-qa-base-v3` creada con SDK + AVD + Appium
- [x] Nested virtualization habilitada (KVM acceleration)
- [x] Ciclo rápido verificado: imagen → emulador → screenshot → shutdown en **~4 min**
- [x] Bug de `nohup` encontrado y corregido
- [x] Emulador Android 14 confirmado funcionando
- [x] ADB detecta `sys.boot_completed=1` en ~50 segundos desde inicio del emulador
- [x] **Salesforce (`chatter` 260.050.0) instalado y lanza sin crash**
- [x] **CG Cloud (`offlineapp` 260.0006.00) instalado y lanza sin crash (traducción arm64)**
- [x] **Snapshot `default_boot` guardado con apps**
- [x] **Imagen `android-qa-base-v5` creada con ambos apps preinstalados**

---

## Próximos Pasos

### 1. Test Appium de login
- Path en VM: `/opt/tests/salesforce_login.js`
- Objetivo: login con usuario/password en Salesforce Mobile y/o CG Cloud
- Ver también: Permission Set "QA MFA Waiver" en Salesforce ⏳ pendiente confirmar con equipo

### 2. Actualizar startup de producción
- Que `startup-v7-image-based.sh` apunte a `android-qa-base-v5`

---

## Notas de Arquitectura

**¿Por qué snapshot `default_boot`?**
Los scripts usan `-no-snapshot-save` (no guardan al salir) pero NO `-no-snapshot-load` (cargan snapshot al bootear si existe). Guardar `default_boot` con los apps garantiza que el boot rápido tenga los apps. Además el `userdata-qemu.img` ya persiste los apps (ningún script usa `-wipe-data`), cubriendo también el cold-boot.

**Credenciales MFA en Salesforce Mobile**
Para que el agente pueda loguearse sin intervención humana, se necesita
un Permission Set que exima al usuario QA del MFA. Consultar con el equipo de SF.

---

## Bloqueantes Pendientes

| Item | Responsable | Estado |
|---|---|---|
| Permission Set "QA MFA Waiver" en Salesforce | Axel + equipo SF | ⏳ Pendiente confirmar |
| Test Appium de login | Claude/Axel | ⏳ Próximo |
