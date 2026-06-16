# Infraestructura Mobile QA — VM Android en GCP

> **Última actualización:** 2026-06-16  
> **Estado general:** ✅ Producción funcionando — imagen `android-qa-base-v7`, script `startup-prod-mobile.sh`

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
| Zona | `us-central1-b` (us-central1-a/c/f con stockout frecuente para n2-standard-4) |
| Imagen activa | `android-qa-base-v7` |
| Bucket GCS | `gs://procontacto-claude-qa/` |
| Machine type | `n2-standard-4` |
| CPU platform | `Intel Cascade Lake` (requerido para nested virtualization / KVM) |
| Cloud NAT | Sólo en `us-central1` — VMs con `--no-address` necesitan esta región |

---

## Scripts en GCS

| Script | Ruta | Propósito |
|---|---|---|
| `startup-prod-mobile.sh` | `gs://procontacto-claude-qa/scripts/startup-prod-mobile.sh` | **PRODUCCIÓN** — startup script multi-proyecto |
| `login2.mjs` | `gs://procontacto-claude-qa/scripts/mobile/login2.mjs` | Login Appium (maneja sesión activa desde snapshot) |
| `test_CMIV2_CMIV2-3526.mjs` | `gs://procontacto-claude-qa/scripts/mobile/` | Suite de TCs por issue |

---

## Imagen `android-qa-base-v7` — Contenido

**Incluye:**
- Android SDK completo
- AVD `test_avd` — Android 34, `google_apis`, `x86_64`
- Snapshot `cmiv2_synced` — estado post-sync del org CMIV2 (~15 min data)
- Appium
- ADB (`/android/platform-tools/adb`)
- Nested virtualization habilitada en la imagen base

---

## Patrón Correcto para Crear VMs (Python API)

```python
from google.cloud import compute_v1

instance = compute_v1.Instance(
    name=vm_name,
    machine_type=f"zones/{zone}/machineTypes/n2-standard-4",
    # CRÍTICO: habilitar nested virtualization para KVM
    advanced_machine_features=compute_v1.AdvancedMachineFeatures(
        enable_nested_virtualization=True,
    ),
    disks=[compute_v1.AttachedDisk(
        boot=True, auto_delete=True,
        initialize_params=compute_v1.AttachedDiskInitializeParams(
            source_image="projects/procontacto-claude/global/images/android-qa-base-v7",
            disk_size_gb=50))],
    network_interfaces=[compute_v1.NetworkInterface(
        network="global/networks/default",
        # Sin access_configs = sin IP externa (usa Cloud NAT)
    )],
    metadata=compute_v1.Metadata(items=[
        compute_v1.Items(key="startup-script-url",
                         value="gs://procontacto-claude-qa/scripts/startup-prod-mobile.sh"),
        # ... resto de parámetros del proyecto
    ]),
    service_accounts=[compute_v1.ServiceAccount(
        email="default",
        scopes=["https://www.googleapis.com/auth/cloud-platform"])],
)
```

**IMPORTANTE:** Sin `enable_nested_virtualization=True`, el emulador falla con:
```
ERROR | x86_64 emulation currently requires hardware acceleration!
CPU acceleration status: KVM requires a CPU that supports vmx or svm
```

---

## Hitos Completados ✅

- [x] Imagen `android-qa-base-v7` con snapshot `cmiv2_synced` (org sincronizado ~15 min data)
- [x] Ciclo completo en producción: VM creada → emulador → snapshot → login → sync → TC → GCS → auto-delete
- [x] `startup-prod-mobile.sh` con parámetros por metadata (multi-proyecto)
- [x] `login2.mjs` maneja sesión activa desde snapshot (activity `.MainActivity` != Login)
- [x] Sync loop detecta "Home detectado" en ~8-9 iteraciones (~3 min desde snapshot)
- [x] TC scripts en `/opt/qa/` descargados frescos desde GCS en cada run

## Bugs Encontrados y Resueltos (2026-06-16)

### BUG 1 — `enable_nested_virtualization` faltante ⚠️ CRÍTICO
**Síntoma:** `adb shell getprop sys.boot_completed` retorna `''` eternamente; emu.log muestra `KVM requires hardware acceleration`.  
**Causa:** VMs creadas sin `AdvancedMachineFeatures.enable_nested_virtualization=True`.  
**Efecto:** Emulador no arranca. Todos los runs fallaban silenciosamente.  
**Fix:** Siempre crear VMs con `AdvancedMachineFeatures(enable_nested_virtualization=True)` via Python API, o `--enable-nested-virtualization` en gcloud CLI.

### BUG 2 — `login2.mjs` asume pantalla de login
**Síntoma:** `No encontré la ventana de login de Salesforce` cuando el snapshot carga con sesión activa.  
**Causa:** `gotoSF()` retorna `false` cuando no hay webview de login → throw sin verificar actividad actual.  
**Fix:** Antes y después de `gotoSF()`, verificar `getCurrentActivity()` — si no incluye "Login", el usuario ya está logueado.

### BUG 3 — `adb` no en PATH para TC scripts
**Síntoma:** `adb: not found` en los scripts de TC cuando usan `execSync('adb ...')`.  
**Causa:** `startup-prod-mobile.sh` define `ADB=/android/platform-tools/adb` pero no exporta PATH.  
**Fix:** Agregar `export PATH="/android/platform-tools:/android/emulator:$PATH"` al inicio del script.

### BUG 4 — Race condition package manager
**Síntoma:** `monkey: No activities found to run` cuando el emulador bootea rápido.  
**Causa:** El monkey corre antes de que el Activity Manager indexe el paquete.  
**Fix:** Loop de verificación `pm list packages | grep $PKG` (hasta 60s) antes del monkey.

## Consideraciones de Seguridad

⚠️ **`set -x` expone credenciales en GCE Serial Console**: `SF_PASS=...` aparece en texto claro.  
Recomendación: usar Secret Manager + cargar en runtime sin exponer en `set -x`.

---

## Notas de Arquitectura

**¿Por qué sin snapshot en el startup script de producción?**  
Se usa `-no-snapshot-save` para evitar corrupción si el emulador es matado abruptamente.
El snapshot se guarda UNA sola vez durante el setup de la imagen, antes de crearla.

**¿Por qué `cmiv2_synced` y no `qa_with_apps`?**  
El snapshot incluye datos del org ya sincronizados (post-login, post-sync). Esto reduce
el tiempo de sync en producción de ~15 min a ~3 min.

**Watchdog de 60 min**  
Un proceso background mata la VM si el script no termina en 60 min. Esto evita VMs
"stuck" que seguirían cobrando. Se cancela en el paso 7 si la eliminación normal funciona.
