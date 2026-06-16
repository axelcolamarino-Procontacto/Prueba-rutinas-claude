# Infraestructura Mobile QA — VM Android en GCP

> **Última actualización:** 2026-06-16  
> **Estado general:** ⚠️ Bug activo en startup script — Pixel Launcher ANR bloquea sync

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
| Imagen activa | `android-qa-base-v7` |
| Bucket GCS | `gs://procontacto-claude-qa/` |
| Machine type | `n2-standard-4` |
| CPU platform | `Intel Cascade Lake` (requerido para nested virtualization / KVM) |

---

## Scripts en GCS

| Script | Ruta | Propósito |
|---|---|---|
| `startup-prod-mobile.sh` | `gs://procontacto-claude-qa/scripts/startup-prod-mobile.sh` | Producción: boot + login + sync + tests + shutdown |
| `setup-emulator.sh` | `gs://procontacto-claude-qa/scripts/setup-emulator.sh` | Inicia emulador, toma screenshot, sube a GCS (sin shutdown — para setup) |
| `appium-install-v2.sh` | `gs://procontacto-claude-qa/scripts/appium-install-v2.sh` | Instala Appium en la VM |

---

## Imagen `android-qa-base-v7` — Contenido

**Incluye:**
- Android SDK completo
- AVD `test_avd` — Android 34, `google_apis` userdebug (`ro.debuggable=1`)
- Appium 3.4.2, UiAutomator2 7.6.0
- ADB (`/android/platform-tools/adb`)
- CG Cloud App Offline instalada y cuenta logueada (`noReset: true`)
- Cloud NAT IP confiada en cada org (34.135.241.169) → sin MFA
- Nested virtualization habilitada (KVM)

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

**Estado al 2026-06-16:** `TERMINATED` (apagada, sin costo)

---

## Bug Activo — Pixel Launcher ANR durante sync (2026-06-16)

**Síntoma:** Al crear una VM efímera con `android-qa-base-v7` (sin imagen pre-sincronizada del proyecto), el emulador muestra el diálogo "Pixel Launcher isn't responding" durante la fase de sync de datos del org. El `startup-prod-mobile.sh` no detecta ni descarta este diálogo, y el sync loop termina en SYNC_TIMEOUT.

**Reproducido en:** 3 VMs consecutivas del run CMIV2-3526 (2026-06-16).

**Causa raíz:** El sync de datos completo (~15 min) genera carga en el emulador que provoca el ANR del Pixel Launcher. El diálogo aparece mientras `login2.mjs` aún está ejecutando, antes de que el sync loop arranque. `uiautomator dump` no lo detecta correctamente en ese contexto.

**Screenshot del bug:** `gs://procontacto-claude-qa/mobile-test/results/CMIV2_CMIV2-3526_20260616_143630.png`

**Fix pendiente en `startup-prod-mobile.sh`:**
Agregar después del paso de unlock (línea ~109) y antes del sync loop:
```bash
# Dismissar diálogos ANR que pueden aparecer durante el boot/login
# Tap en coordenadas del botón "Wait" en 320×640 (aparece ~y=391)
for i in $(seq 1 10); do
  $ADB shell input tap 160 391 2>/dev/null || true
  sleep 2
done
```

**Workaround temporal:** Usar imagen pre-sincronizada del proyecto (`create_snapshot=true` en primer run con sync completo).

**Issue relacionado:** CMIV2-3526 — todos los TCs quedaron en REVIEW por esta causa.

---

## Hitos Completados ✅

- [x] Imagen `android-qa-base-v7` creada con CG Cloud + cuenta logueada
- [x] Nested virtualization habilitada (KVM acceleration)
- [x] Cloud NAT con IP fija (`34.135.241.169`) → sin MFA en todos los orgs
- [x] Bug de `nohup` encontrado y corregido
- [x] Emulador Android 14 confirmado funcionando
- [x] ADB detecta `sys.boot_completed=1` en ~50 segundos desde inicio del emulador
- [x] Pipeline de test mobile E2E funcionando: CMIV2 Productos Iniciales (TC-01/TC-02)
- [x] Auto-eliminación de VM al terminar (costo $0 en reposo)

---

## Próximos Pasos — Infra

### 1. Fix Pixel Launcher ANR (bloqueante para sync completo)
Ver sección "Bug Activo" arriba. Fix en `startup-prod-mobile.sh`.

### 2. Imagen pre-sincronizada por proyecto (opcional)
Para sync rápido (~2 min vs ~15 min), crear imagen post-sync por proyecto:
```bash
gcloud compute instances create qa-mobile-sync-cmiv2 \
  --metadata=create_snapshot=true,snapshot_image_name=android-qa-cmiv2-synced-v1,...
```

---

## Notas de Arquitectura

**¿Por qué sin snapshot en el startup script de producción?**  
Se usa `-no-snapshot-save` para evitar corrupción si el emulador es matado abruptamente.
El snapshot se guarda UNA sola vez durante el setup de la imagen, antes de crearla.

**Cloud NAT — anti-MFA**  
Router `qa-router` (us-central1) + IP estática `qa-nat-ip` = `34.135.241.169`.
Todas las VMs se crean `--no-address` → egreso por Cloud NAT con esa IP → la IP está
confiada en cada org → CG Cloud no pide MFA.

---

## Bloqueantes Pendientes

| Item | Responsable | Estado |
|---|---|---|
| Fix ANR Pixel Launcher en startup-prod-mobile.sh | QA Agent / Axel | ⚠️ Activo |
| Imagen pre-sincronizada por proyecto | QA Agent | ⏳ Pendiente |
