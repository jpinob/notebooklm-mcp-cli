============================================================
REPORTE DE AUDITORÍA DE SEGURIDAD
Proyecto: notebooklm-mcp-cli
Fecha: 2026-02-19
Versión auditada: v0.3.3 (commit 522cc8c)
============================================================

RESUMEN EJECUTIVO
-----------------
- Puntuación: 8.5/10 (post-fix, original 7.5/10)
- Issues Críticos: 0
- Issues Altos: 0 (2 corregidos el 2026-02-19)
- Issues Medios: 2 (1 corregido: .gitignore)
- Issues Bajos: 3

El proyecto tiene una base de seguridad razonable: no hay secretos
hardcodeados, no usa shell=True, el CSRF token se redacta en debug logs,
y los perfiles usan chmod 600/700. Sin embargo, hay gaps en el almacenamiento
de credenciales y en la configuración de .gitignore que deben corregirse
antes de hacer fork público.


============================================================
HALLAZGOS ALTOS (Corregir pronto)
============================================================

1. LEGACY AUTH CACHE SIN PERMISOS RESTRICTIVOS — ✅ CORREGIDO (2026-02-19)
   - Archivo: src/notebooklm_tools/core/auth.py:save_tokens_to_cache()
   - Riesgo ORIGINAL: Cookies escritas sin chmod 600.
   - Corrección aplicada: Añadido chmod 0o600 al archivo y 0o700 al directorio
     padre, con try/except OSError para compatibilidad Windows.
   - Verificación: 331 tests passed.

2. DEBUG LOGGING EXPONE DATOS COMPLETOS DE API — ✅ CORREGIDO (2026-02-19)
   - Archivo: src/notebooklm_tools/core/base.py:_call_rpc()
   - Riesgo ORIGINAL: Request params y response data se logueaban íntegros (2000 chars).
   - Corrección aplicada:
     a) Truncado de debug output reducido de 2000 a 500 chars (request params,
        response data, y error body)
     b) Añadido comentario WARNING en el código documentando que --debug puede
        exponer contenido de usuario
   - El CSRF token ya se redactaba correctamente (sin cambios necesarios).
   - Verificación: 331 tests passed.


============================================================
HALLAZGOS MEDIOS (Corregir en las próximas iteraciones)
============================================================

3. COOKIES ALMACENADAS EN TEXTO PLANO (SIN CIFRADO)
   - Archivo: ~/.notebooklm-mcp-cli/profiles/<name>/cookies.json
   - Archivo: ~/.notebooklm-mcp-cli/auth.json (legacy)
   - Riesgo: Las cookies de Google se almacenan como JSON en texto plano.
     Si un atacante obtiene acceso al filesystem del usuario, puede robar
     las cookies y suplantar la sesión de Google NotebookLM.
   - Mitigación actual: chmod 0o600 en profiles (no en legacy auth.json)
   - Solución futura: Cifrar cookies en disco usando cryptography (Fernet)
     con clave derivada del sistema (DPAPI en Windows, keyring en macOS/Linux).

4. CHROME --remote-allow-origins=* EN AUTENTICACIÓN
   - Archivo: src/notebooklm_tools/utils/cdp.py:157
   - Riesgo: Al lanzar Chrome para login, se usa --remote-allow-origins=*
     que permite que cualquier proceso local se conecte al puerto de debugging
     de Chrome durante la autenticación. Un proceso malicioso en la misma
     máquina podría conectarse al CDP y extraer cookies.
   - Mitigación: El puerto solo está abierto durante el flujo de login.
   - Solución: Restringir a --remote-allow-origins=http://localhost:{port}
     o al menos documentar el riesgo.

5. .gitignore INCOMPLETO PARA ARCHIVOS SENSIBLES — ✅ CORREGIDO (2026-02-19)
   - Archivo: .gitignore
   - Riesgo ORIGINAL: Faltan patrones para archivos de secretos comunes que podrían
     ser creados accidentalmente en el proyecto.
   - Patrones faltantes:
     - .env / .env.* / *.env (archivos de variables de entorno)
     - secrets/ / credentials/ (directorios de secretos)
     - *.token (archivos de tokens)
     - *.cookie (archivos de cookies adicionales)
   - Solución: Añadir estos patrones al .gitignore (ver sección Recomendaciones).


============================================================
HALLAZGOS BAJOS (Mejoras opcionales)
============================================================

6. USER-AGENT HARDCODEADO COMO macOS
   - Archivo: src/notebooklm_tools/core/base.py:339
   - Riesgo: El User-Agent siempre se identifica como macOS independientemente
     del sistema real. Riesgo mínimo (fingerprinting), pero podría causar
     comportamiento inesperado si Google filtra por UA.
   - Solución: No urgente. Considerar detectar el OS real o usar un UA genérico.

7. NO EXISTE .env.example NI DOCUMENTACIÓN DE VARIABLES DE ENTORNO
   - Riesgo: Las variables de entorno (NOTEBOOKLM_COOKIES, etc.) están
     documentadas en código pero no hay un .env.example que sirva de guía.
     Un usuario podría crear un .env con cookies reales y commitearla.
   - Solución: Crear .env.example con placeholders y asegurar .env en .gitignore.

8. MCP save_auth_tokens ACEPTA INPUT SIN LÍMITE DE LONGITUD
   - Archivo: src/notebooklm_tools/mcp/tools/auth.py:82-85
   - Riesgo: El parsing de cookies (split("; ") + split("=", 1)) no tiene
     límite de longitud. Un input masivo podría causar uso excesivo de memoria.
   - Mitigación: La superficie de ataque es limitada (solo MCP clients locales).
   - Solución: Añadir un límite razonable al tamaño del input.


============================================================
PRÁCTICAS POSITIVAS ENCONTRADAS
============================================================

✅ Sin shell=True en ningún subprocess - Chrome y CLI setup usan listas de args
✅ CSRF token redactado en debug logs (core/utils.py:82 → "(csrf_token)")
✅ Perfiles de auth con chmod 0o600 (cookies.json) y 0o700 (directorio)
✅ Sin credenciales hardcodeadas ni API keys en código fuente
✅ Sin rutas absolutas con username en código fuente
✅ Sin secretos encontrados en historial de git
✅ Debug logging deshabilitado por defecto (level=WARNING)
✅ Cookies solo se envían a dominios de Google (.google.com, .googleusercontent.com)
✅ Filtrado de cookies esenciales (solo auth-relevant se guardan)
✅ cookies.txt y .notebooklm*/ en .gitignore
✅ Sin dependencias con vulnerabilidades críticas conocidas en core deps
✅ Retry auth con recovery de 3 capas (CSRF refresh → disk reload → headless)


============================================================
ANÁLISIS DE ALMACENAMIENTO
============================================================

Ubicación: ~/.notebooklm-mcp-cli/
├── auth.json                          → Cookies en texto plano (legacy, sin chmod)
├── config.toml                        → Config (no sensible)
├── aliases.json                       → Aliases de notebooks (no sensible)
├── profiles/<name>/
│   ├── cookies.json                   → Cookies en texto plano (chmod 0o600 ✅)
│   └── metadata.json                  → CSRF token, session ID (chmod 0o600 ✅)
├── chrome-profile/                    → Perfil Chrome dedicado (contiene sesión Google)
└── chrome-profiles/<name>/            → Perfiles Chrome por cuenta

Riesgo principal: Las cookies son equivalentes a una sesión de Google activa.
Un atacante con acceso a estos archivos tiene acceso completo a NotebookLM
del usuario (y potencialmente a otros servicios de Google si las cookies
incluyen scopes amplios).


============================================================
ANÁLISIS DE DEPENDENCIAS (Core)
============================================================

Dependencia         Versión    Estado    Notas
─────────────────────────────────────────────────────────
httpx               0.27.2     OK        HTTP client
pydantic            2.9.2      OK        Validación
typer               0.17.4     OK        CLI framework
rich                13.5.3     OK        Terminal formatting
websocket-client    1.8.0      OK        CDP connection
platformdirs        4.3.8      OK        OS paths
fastmcp             >=0.1.0    OK        MCP server

No se detectaron vulnerabilidades críticas conocidas en las dependencias
core. Las dev deps (pytest, ruff, mypy) no se incluyen en producción.


============================================================
ANÁLISIS DE INYECCIONES
============================================================

SQL Injection:       N/A - No hay base de datos
Command Injection:   ✅ No se usa shell=True
                     ✅ subprocess.Popen con lista de args
                     ✅ subprocess.run con lista de args
XSS:                 N/A - No hay frontend web
                     (El server HTTP expone solo JSON via FastMCP)
Path Traversal:      Bajo riesgo - downloads van a rutas específicas


============================================================
RECOMENDACIONES (Ordenadas por prioridad)
============================================================

1. [ALTO] Añadir chmod 0o600 a save_tokens_to_cache() en core/auth.py:129
   para igualar la protección del flujo de perfiles.

2. [ALTO] Documentar que --debug puede exponer contenido de notebooks en logs.
   Opcionalmente, añadir flag --debug-redact que trunce respuestas grandes.

3. [MEDIO] Reforzar .gitignore con patrones de secretos adicionales:
   ```
   # Environment and secrets
   .env
   .env.*
   *.env
   secrets/
   credentials/
   *.token
   *.cookie
   ```

4. [MEDIO] Considerar pre-commit hook con detect-secrets o patrón propio
   para evitar commits accidentales de cookies/tokens.

5. [MEDIO] Evaluar cifrado de cookies en disco con cryptography (Fernet)
   para futura iteración de seguridad.

6. [BAJO] Cambiar --remote-allow-origins=* a --remote-allow-origins=http://localhost
   en cdp.py:157 para limitar superficie de ataque durante login.

7. [BAJO] Crear .env.example con placeholders documentados.


============================================================
HISTORIAL DE GIT - VERIFICACIÓN DE SECRETOS
============================================================

Se verificaron los siguientes patrones en todo el historial de git:
- Archivos .env: Ninguno encontrado
- Patrón "password" en código: Solo referencia a documentación (config.py:199)
- Patrón "AKIA" (AWS keys): Ninguno encontrado
- Patrón "sk-" (OpenAI/Stripe): Solo en docs/prompts (ejemplo de patrones)
- Patrón "ghp_" (GitHub tokens): Solo en docs/prompts (ejemplo de patrones)
- Patrón "Bearer": Solo en docs/prompts (ejemplo de patrones)

Resultado: ✅ Sin secretos filtrados en historial de git


============================================================
FIN DEL REPORTE
============================================================
