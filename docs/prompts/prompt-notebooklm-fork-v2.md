# Proyecto: Fork y mejora de notebooklm-mcp-cli

## Contexto
Vamos a hacer fork y mejorar el proyecto https://github.com/jacob-bd/notebooklm-mcp-cli (v0.2.11, MIT License, Python).

Es un servidor MCP + CLI que da acceso programático a Google NotebookLM. Permite crear notebooks, añadir fuentes, hacer queries, generar audio/video y más.

**Mi objetivo:** Usarlo como base de conocimiento verificadora conectada a Claude Code vía MCP. Tengo suscripción MAX de Claude. Quiero poder consultar mis notebooks de NotebookLM desde Claude Code para contrastar información con fuentes curadas.

**Mi entorno:** Windows 11, Claude Code, Python con uv, Git.

---

## ⚠️ SEGURIDAD — PRIORIDAD MÁXIMA (Lee esto ANTES de cualquier otra cosa)

### Principios inquebrantables
1. **NUNCA commitear secretos, cookies, tokens, API keys ni credenciales al repositorio.**
2. **NUNCA loguear cookies, tokens o credenciales en stdout, stderr ni archivos de log.**
3. **NUNCA hardcodear rutas con mi username, email o datos personales en código fuente.**
4. **Antes de CADA commit, verificar que no hay secretos filtrados.**

### Fase 0 — Auditoría de seguridad (ANTES de tocar código)
1. **Analizar qué almacena el proyecto y dónde:**
   - `~/.notebooklm-mcp-cli/` — ¿qué archivos hay? ¿cookies? ¿tokens? ¿en texto plano?
   - Perfil de Chrome dedicado — ¿dónde se guarda? ¿qué contiene?
   - Archivos temporales — ¿se crean? ¿se limpian?
2. **Auditar el código fuente buscando:**
   - Credenciales hardcodeadas
   - Logging que imprima tokens/cookies (buscar `print`, `logging`, `logger` cerca de `cookie`, `token`, `csrf`, `auth`)
   - Rutas absolutas con datos de usuario
   - Requests HTTP que envíen credenciales a terceros
   - Dependencias con vulnerabilidades conocidas (`uv pip audit` o equivalente)
3. **Documentar hallazgos en SECURITY_AUDIT.md** antes de continuar

### .gitignore — Obligatorio desde el minuto cero
Verificar y reforzar el `.gitignore` con al menos:
```
# Credenciales y secretos
.env
.env.*
*.env
secrets/
credentials/
cookies.txt
*.cookie
*.token

# NotebookLM auth data
.notebooklm-mcp-cli/

# Chrome profiles
chrome-profile/
chrome-data/

# Logs que puedan contener tokens
*.log
logs/

# OS y editor
.DS_Store
Thumbs.db
*.swp
*.swo
.idea/
.vscode/settings.json
*.pyc
__pycache__/
*.egg-info/
dist/
build/

# Archivos temporales
tmp/
temp/
*.tmp
```

### Pre-commit hook — Detección de secretos
Configurar un pre-commit hook que:
1. Escanee archivos staged buscando patrones de secretos:
   - Cookies (`SID=`, `HSID=`, `SSID=`, `__Secure-`, `NID=`)
   - Tokens (`token=`, `csrf`, `Bearer `)
   - API keys (patrones `AIza`, `sk-`, `ghp_`, etc.)
   - Emails personales
   - Rutas con username de Windows (`C:\Users\<username>`)
2. Bloquee el commit si detecta algo sospechoso
3. Usar `detect-secrets` o similar si está disponible en Windows

### Mejoras de seguridad al código (Fase posterior)
1. **Cifrar cookies en disco** — usar `cryptography` (Fernet) con clave derivada del sistema
2. **Permisos de archivo** — las cookies deben tener permisos restrictivos (equivalente a 600 en Linux)
3. **Limpieza de logs** — sanitizar cualquier output que pueda contener tokens
4. **Variables de entorno** para configuración sensible (nunca en código)
5. **Timeout de sesión** — invalidar cookies locales después de X tiempo
6. **Documentar** en README las implicaciones de seguridad para otros usuarios

### Si el fork va a ser público
- ⚠️ Revisar CADA archivo antes del primer push
- ⚠️ No incluir datos de mi cuenta de Google en tests ni docs
- ⚠️ Usar datos mock/ficticios para ejemplos y tests
- ⚠️ Considerar hacer el fork privado inicialmente y hacerlo público solo después de la auditoría

---

## Plan de mejoras (por fases)

### Fase 0 — Auditoría de seguridad (PRIMERO)
1. Ejecutar la auditoría descrita arriba
2. Configurar `.gitignore` reforzado
3. Instalar pre-commit hook de detección de secretos
4. Documentar hallazgos en SECURITY_AUDIT.md
5. Solo después de esto, continuar con Fase 1

### Fase 1 — Setup
1. Fork del repo en mi GitHub (PRIVADO inicialmente)
2. Clonar localmente
3. Instalar dependencias con `uv`
4. Autenticar con `nlm login`
5. Probar que funciona: `nlm notebook list`
6. Registrar el MCP: `claude mcp add --scope user notebooklm-mcp notebooklm-mcp`
7. Documentar cualquier problema en Windows

### Fase 2 — Explorar código fuente
1. Analizar la arquitectura del proyecto (src/, tests/, scripts/)
2. Mapear los 29 tools MCP y sus funciones
3. Identificar puntos débiles y oportunidades de mejora
4. Crear un ARCHITECTURE.md con el mapa del código

### Fase 3 — Tests con pytest
1. Analizar los tests existentes en tests/
2. Diseñar suite de tests: unit + integration
3. Implementar tests para los tools MCP principales
4. **Tests NUNCA deben usar credenciales reales** — usar mocks/fixtures
5. Configurar CI con GitHub Actions
6. Alcanzar cobertura mínima razonable

### Fase 4 — Mejorar query y respuestas
1. Mejorar `notebook_query` para devolver respuestas más estructuradas a Claude Code
2. Añadir contexto de fuentes en las respuestas (qué fuente dice qué)
3. Formato optimizado para consumo por LLM (no solo humanos)

### Fase 5 — Organización de notebooks
1. Sistema de tags/categorías para notebooks temáticos
2. Poder consultar notebooks por dominio (ej: "Playwright", "Docker", "AI Agents")
3. Query cross-notebook (buscar en varios notebooks a la vez)

### Fase 6 — Contribuir upstream
1. Preparar PRs con mejoras Windows + tests + seguridad
2. Documentar cambios en CHANGELOG

---

## Reglas
- Estamos en Windows 11. Verifica compatibilidad siempre.
- Usa `uv` como package manager (no pip directo).
- Commits en inglés, comentarios en código en inglés.
- Tests con pytest. Tests NUNCA con credenciales reales.
- Si algo no funciona en Windows, documéntalo antes de buscar workaround.
- No asumas nada sobre las APIs internas de NotebookLM. Lee el código primero.
- **SEGURIDAD: ante la duda, pregúntame antes de hacer commit o push.**

## Empieza por
Fase 0: Clona el repo y ejecuta la auditoría de seguridad completa. Muéstrame los hallazgos ANTES de continuar con nada más.
