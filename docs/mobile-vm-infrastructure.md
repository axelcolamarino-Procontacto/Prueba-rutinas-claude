# Infraestructura Mobile QA — VM Android en GCP

> **Última actualización:** 2026-06-04
> **Estado general:** ✅✅ **Login mobile de CG Cloud 100% AUTOMATIZADO** (probado end-to-end). Imagen userdebug + Appium webview + Cloud NAT + IP confiada. Ver "SOLUCIÓN — Login automático".

---

## ✅ SOLUCIÓN — Login automático mobile (RESUELTO 2026-06-04)

El login de CG Cloud quedó **100% automatizado**, sin intervención humana. Probado: la app loguea y empieza a sincronizar datos del org (CMI staging). Las 4 piezas:

1. **Imagen de sistema `google_apis` (userdebug), NO `google_apis_playstore`**
   - Causa raíz del bloqueo anterior: playstore = build `user` (`ro.debuggable=0`) → webview debugging APAGADO → Appium no veía el webview de login.
   - `google_apis` = `userdebug` (`ro.debuggable=1`) → **webview debugging AUTO-ON** para todas las apps → Appium entra al webview. (Play Store no se necesita: los APK se sideloadean.)
   - AVD recreado: `avdmanager create avd -n test_avd -k "system-images;android-34;google_apis;x86_64" --force`

2. **Appium driltea el webview de login por window handle**
   - El login OAuth de SF es una *página* (window handle) distinta del Cordova interno de la app ("Clockwork Framework", `file:///android_asset/www/index.html`).
   - Flujo: `getContexts` → switch a `WEBVIEW_*` → `getWindowHandles` → switch al handle cuya URL tiene `salesforce.com` → `#username` / `#password` / `#Login`.
   - Server Sandbox: menú ⋮ → Change Server → Sandbox (nativo, vía uiautomator2).
   - Appium server: `--allow-insecure=uiautomator2:chromedriver_autodownload` (baja chromedriver 113 para el webview).
   - Script: `/opt/qa/login2.mjs` (webdriverio). Apps helper de Appium se instalan solas.

3. **Cloud NAT con IP estática de egreso → IP confiada en Salesforce**
   - La verificación de identidad por email se dispara por IP desconocida. (El permiso "Skip Device Activation" NO la suprime — la IP es la palanca.)
   - **Cloud NAT** (`qa-nat` / router `qa-router` / IP `qa-nat-ip` = **`34.135.241.169`**) da una IP de egreso fija a TODAS las VMs efímeras (sin IP externa propia) → escala multi-proyecto y concurrente.
   - Esa IP se carga como **Login IP Range** en el perfil `CGCloud_User_Profile` (o Trusted IP Range org-wide), **una vez por org/proyecto**.
   - Con la IP confiada → login directo sin verificación.

4. **MFA exento:** PS `QA_MFA_Waiver` (BypassMFAForUiLogins + SkipIdentityConfirmation) en el user QA.

### ⚠️ Detalle crítico: PIN + cold boot
La app exige lock screen (PIN 1234, fix U1006). Pero en **cold boot el device arranca BLOQUEADO** → ni `io.appium.settings` ni la app arrancan ("Appium Settings app is not running"). **Hay que desbloquear con el PIN tras el boot** antes de correr Appium:
```bash
$ADB shell input keyevent KEYCODE_WAKEUP; $ADB shell input swipe 200 600 200 150
$ADB shell input text 1234; $ADB shell input keyevent KEYCODE_ENTER
```
(Con snapshot-boot que restaura estado desbloqueado no haría falta, pero el startup debe contemplarlo.)

### Acceso SSH sin IP externa
VMs sin IP externa (para egresar por NAT) → SSH por **IAP** (`--tunnel-through-iap`). Requiere rol `roles/iap.tunnelResourceAccessor` (ya otorgado a axel). En producción el test corre por startup script, sin SSH.

---

## Runner de producción (multi-proyecto)

**`startup-prod-mobile.sh`** (`gs://procontacto-claude-qa/scripts/startup-prod-mobile.sh`) es el orquestador que corre en el **boot de la VM**. Flujo: boot emulador → desbloquear PIN → Appium → baja scripts de test de GCS → login → evidencia a GCS → apaga la VM.

**Multi-proyecto:** los datos que cambian por proyecto se pasan como **metadata de la instancia** (NO van en la imagen ni en el script):

| metadata | qué es |
|---|---|
| `sf_user` / `sf_pass` | credenciales del usuario QA **de ese proyecto** |
| `project_key` / `issue_key` | para nombrar los resultados |
| `app` | `offlineapp` (CG Cloud) o `chatter` (Salesforce) |

Los **scripts de test** (`login2.mjs`, futuros `test_*.mjs`) viven en `gs://.../scripts/mobile/` y se bajan frescos en cada run → se actualizan **sin re-hornear la imagen**. La imagen v7 solo aporta el runtime (AVD, apps, Appium, node, webdriverio en `/opt/qa`).

### Lanzar un test de un proyecto (ejemplo)
```bash
gcloud compute instances create qa-mobile-$RANDOM \
  --zone=us-central1-a --image=android-qa-base-v7 \
  --machine-type=n2-standard-4 --min-cpu-platform="Intel Cascade Lake" \
  --enable-nested-virtualization \
  --no-address \   # SIN IP externa -> egresa por Cloud NAT (IP confiada)
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --metadata=startup-script-url=gs://procontacto-claude-qa/scripts/startup-prod-mobile.sh,sf_user=USUARIO@proyecto.sandbox,sf_pass=PASSWORD,project_key=CMIV2,issue_key=CMI-123,app=offlineapp
```
La VM se crea, corre el login/test sola, sube resultados a `gs://.../mobile-test/results/<proyecto>_<issue>_<ts>.{log,png}` y se apaga.

> 🔐 **Credenciales:** hoy van por metadata (simple, sirve para sandboxes). Para endurecer, migrar a **Secret Manager** (metadata solo con el nombre del secreto; la VM lo resuelve con su SA).
>
> 🌐 **Por cada proyecto nuevo:** confiar la IP `34.135.241.169` (Cloud NAT) en esa org (Login IP Range en el perfil QA o Trusted IP Range). Una vez por org.
>
> 📱 **`chatter` (Salesforce app):** `login2.mjs` está validado para CG Cloud (`offlineapp`). La app Salesforce NO es automatizable en emulador — ver sección siguiente.

---

## ✅ App Salesforce común (`com.salesforce.chatter`) — RASP RESUELTO con build oficial

**El problema del RASP se resuelve usando el build de desarrollo oficial de Salesforce — NO hay que bypassear nada.**

### El problema (con el APK de Play Store)
- `com.salesforce.chatter` v250020020 de Play Store/APKPure → **crashea al inicio** (`ktegnp.D: !null` + segfault nativo).
- Confirmado que es **RASP/anti-tamper** (paquete `com.salesforce.android.compliance.security`): crashea con x86_64 y arm64, y **sin** Appium → detecta el emulador/`ro.debuggable=1`.
- Bypass con **Frida intentado y fallido** (RASP nativo ofuscado, probablemente comercial Promon/Guardsquare con anti-Frida).

### La solución (build oficial `externalDev`) ✅ PROBADO
Salesforce publica un **build de emulador/desarrollo de la app SIN el RASP**, hecho justo para correr en emulador y automatizar con Appium:
- **Fuente:** Salesforce Mobile Debugging Tools → https://developer.salesforce.com/tools/mobile-debugging
- **Shortlink Android:** `sfdc.co/salesforce-mobile-app-android-emulator`
- **APK directo (v260.040.0):** `https://developer.salesforce.com/files/sfmobiletools/SalesforceApp-Android-260.040.0%236-s1-externalDev.apk`
- Respaldado por el blog oficial: *"Automated Testing with the Salesforce Mobile App & Appium"* (developer.salesforce.com/blogs/2021/08).

**Probado (2026-06-05):** el build `externalDev` instala (`com.salesforce.chatter`), **arranca SIN crashear**, acepta EULA (`ChatterLoginEulaActivity` → "I AGREE" en ~(289,48)) y llega al **login** (`ChatterLoginActivity`). Los campos del login (`username`, `password`, `Login`) son accesibles. Hay **"Use Custom Domain"** para apuntar al sandbox.

### Pasos para completar el login de chatter (mismo patrón que CG Cloud)
1. Instalar el build `externalDev` (no el de Play Store) → subir a `gs://.../apks/`.
2. Lanzar `com.salesforce.chatter/.Chatter` → tap **"I AGREE"** (EULA).
3. **"Use Custom Domain"** → ingresar `corporacionmultiinversiones--staging.sandbox.my.salesforce.com` → Continue. (O cambiar server a Sandbox.)
4. Appium webview: `#username` / `#password` / `#Login` (igual que CG Cloud).
5. Verificación de identidad: cubierta por la **IP NAT confiada** — ⚠️ pero el user `...cmiprod.staging` es **System Administrator**, no `CGCloud_User_Profile`. Si la IP se confió solo en ese perfil, hay que confiarla también para System Administrator (o usar **Trusted IP Ranges org-wide**).

> Conclusión: la app Salesforce común **SÍ es automatizable** — con el build oficial externalDev, no con el de Play Store (que tiene RASP).

### Progreso del login chatter (2026-06-05) — autentica, pero el callback OAuth nativo no cierra
- ✅ El build `externalDev` corre, EULA OK, llega al login.
- ✅ **Las credenciales AUTENTICAN en la org**: con server picker nativo → Sandbox (test.salesforce.com) o My Domain, el form `#username`/`#password`/`#Login` (tipeo real) entra y se ve la org (Axel Colamarino / Sandbox: Staging / tabs Home, **Leads**, Accounts…). Sin verificación (IP NAT confiada funciona).
- ⚠️ **PERO no llega a `MainActivity` (app nativa).** El callback OAuth `sfdc://` no se completa → queda en `ChatterLoginActivity`. Causas que lo hacen muy frágil:
  - Usar el `#mydomain` del webview hace redirect plano → rompe el contexto OAuth (queda sesión web, no token).
  - El default del build es `welcome.salesforce.com` (discovery, **shadow DOM** → no automatable por querySelector).
  - Cookies de sesiones previas en el My Domain → la página no muestra el form de login.
  - `pm clear` resetea server (a welcome) y EULA; seleccionar Sandbox manda la app a background un instante → falla el attach de Appium.
- **Camino correcto identificado:** server picker NATIVO del SDK (menú ⋮ → **Change Server** → **Sandbox**, que preserva el OAuth) + cookies limpias + llenar `#username` directo (sin `#mydomain`). No convergió por la combinación de timing/estado + inestabilidad del entorno.
- ⛔ **Video:** el login webview es `FLAG_SECURE` (no grabable). Para grabar habría que llegar a `MainActivity` (nativo, grabable como CG Cloud), que es justo lo que no se logró cerrar.

**Artefactos guardados:** `gs://procontacto-claude-qa/apks/salesforce-chatter-externalDev.apk` y `gs://.../scripts/mobile/chatter_login.mjs`.

**Recomendación:** para QA mobile con video usar **CG Cloud** (login nativo 100% + grabable). Para Salesforce común, **web (Lightning + Playwright)**. El login nativo de chatter queda como pendiente avanzado (requiere más trabajo sobre el flujo OAuth/welcome de SF).

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
| **Imagen activa** | **`android-qa-base-v7`** (userdebug + apps + PIN + Sandbox + Appium + scripts `/opt/qa` + snapshot desbloqueado + login automatizado). `v5`/`v6` = playstore obsoletas (sin webview debugging) |
| Cloud NAT | router `qa-router` + nat `qa-nat`, IP egreso **`34.135.241.169`** (confiar en cada org) |
| VMs de test | crear **sin IP externa** (`--no-address`) → egresan por NAT. SSH por IAP |
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

## Imagen `android-qa-base-v6` — Agregados sobre v5 (2026-06-04)

- **PIN de dispositivo `1234`** (`adb shell locksettings set-pin 1234`). CG Cloud (datos offline cifrados) exige lock screen; sin PIN tira *"The device is insecure... (Code: U1006)"*. Con PIN, pasa.
- **CG Cloud server = Sandbox** (`https://test.salesforce.com`). Por defecto apuntaba a producción (`login.salesforce.com`). Se cambió desde el login: menú ⋮ (arriba der.) → **Change Server** → **Sandbox**. El picker es nativo (no FLAG_SECURE).
- **Permisos runtime concedidos** a CG Cloud (`pm grant`: CAMERA, location, contacts/GET_ACCOUNTS, media, bluetooth, etc.) → no aparecen diálogos al abrir.
- **Driver Appium `uiautomator2@7.6.0`** instalado (`appium driver install uiautomator2`).
- Snapshot `default_boot` re-guardado capturando todo lo anterior.

---

## ⚠️ Login automático mobile — Hallazgo / Bloqueante

**El login de credenciales de CG Cloud (y Salesforce mobile) NO se puede automatizar con herramientas estándar.** El login es un **WebView OAuth de Salesforce** (`CustomLoginActivity`, resource `sf__oauth_webview`) con 3 candados simultáneos:

1. **`FLAG_SECURE`** → `screencap`/`screenrecord` devuelven **negro/0 bytes**. No hay screenshots ni grabación de la pantalla de login.
2. **WebView `NAF=true`** (Not Accessibility Friendly) → `uiautomator` **no ve** los campos usuario/contraseña (solo el contenedor WebView).
3. **WebView debugging DESHABILITADO** (APK release) → no hay socket `@webview_devtools_remote_*` → **Appium no puede entrar al contexto WebView** (chromedriver se conecta por ese socket).

**Prueba definitiva (Appium):** sesión UiAutomator2 sobre la app → `GET /contexts` devuelve **`["NATIVE_APP"]`** únicamente (sin `WEBVIEW_*`).

> Conclusión: tapear "a ciegas" por coordenadas es inviable (no se ve nada y el flujo SF es de 2 pasos). Appium sirve para las pantallas **nativas** (post-login) pero NO para el webview de login.

**MFA:** resuelto aparte — Permission Set `QA_MFA_Waiver` (BypassMFAForUiLogins + SkipDeviceActivation) en CMI staging, asignado a `axel.colamarino@appoffline.com.mx` y `...cmiprod.staging`. (El MFA NO era el bloqueante; el webview sí.)

### Camino recomendado para el login
**Login manual UNA vez + hornear sesión en la imagen.** El Salesforce Mobile SDK guarda el refresh token en el store cifrado de la app; una vez logueado, la sesión persiste. Pasos:
1. Exponer el emulador a una pantalla remota (scrcpy vía túnel SSH del adb, o VNC en la VM).
2. Axel hace el login manual una vez (usuario/pass; MFA ya exento).
3. Guardar snapshot + crear imagen v7 con la sesión activa.
4. Los tests Appium corren **post-login** (pantallas nativas de CG Cloud) reusando la sesión.

Alternativas descartadas: token injection (store cifrado device-bound), build debuggable de CG Cloud (no disponible), OCR sobre screenshot (bloqueado por FLAG_SECURE).

---

## Próximos Pasos

### 1. Login manual one-time + imagen v7 con sesión (ver sección de arriba)
- scrcpy/VNC → login manual → snapshot → `android-qa-base-v7`

### 2. Test Appium de las pantallas nativas post-login
- Una vez con sesión activa, automatizar el flujo real de CG Cloud (nativo) con uiautomator2.

### 3. Actualizar startup de producción
- Que `startup-v7-image-based.sh` apunte a `android-qa-base-v6` (o v7 cuando exista).

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
