---
name: nlm-debug-protocol
description: Guía para debuggear problemas con el protocolo batchexecute de NotebookLM. Activar cuando hay errores de API, respuestas vacías, fallos de autenticación, o comportamiento inesperado de la API. Ejemplos: "error 401", "la API no responde", "respuesta vacía", "no funciona el RPC", "auth failure", "CSRF expired".
---

# Debug Protocol — NotebookLM Batchexecute

Guía para diagnosticar y resolver problemas con la API interna de NotebookLM.

## Paso 1: Habilitar debug logging

```bash
# MCP server con debug
notebooklm-mcp --debug

# O via variable de entorno
NOTEBOOKLM_MCP_DEBUG=true notebooklm-mcp
```

Esto activa logging detallado en stderr:
- RPC ID y nombre del método
- Parámetros del request (decodificados)
- Response status y datos
- CSRF token redactado como `(csrf_token)`

## Paso 2: Identificar el tipo de error

### Error de autenticación (401/403 HTTP o RPC Error 16)

**Síntomas:**
- `HTTPStatusError: 401 Unauthorized`
- `HTTPStatusError: 403 Forbidden`
- `AuthenticationError: Authentication expired`

**Diagnóstico:**

```
¿El error ocurre en la PRIMERA llamada?
  → Las cookies están expiradas
  → Solución: `nlm login`

¿El error ocurre DESPUÉS de funcionar un rato?
  → El CSRF token expiró (normal, se auto-refresca)
  → El retry automático debería manejarlo (3 capas)
  → Si falla: cookies expiradas → `nlm login`
```

**Capas de recovery (automático):**

```
Capa 1: _refresh_auth_tokens()    → Re-extrae CSRF + session ID de la página
Capa 2: _try_reload_or_headless() → Recarga cookies de disco
Capa 3: run_headless_auth()       → Re-autentica via Chrome headless
```

Si las 3 capas fallan → cookies completamente expiradas → `nlm login`

### Respuesta vacía o None

**Síntomas:**
- Función retorna `None` o lista vacía
- `ServiceError: No data in response`

**Diagnóstico:**

```python
# 1. Verificar que el RPC ID es correcto
# Cada endpoint tiene su propio RPC ID (string de 6 chars)
# Ver src/notebooklm_tools/core/utils.py para el mapping completo

# 2. Verificar estructura de parámetros
# Los parámetros son posicionales en listas anidadas
# Un parámetro en la posición incorrecta → respuesta vacía

# 3. Con --debug, ver la respuesta raw:
# logger.debug("Response Data: [...]")
# Si la respuesta es una lista vacía → parámetros incorrectos
# Si la respuesta tiene datos pero el parsing falla → ajustar índices
```

### Error de parsing de respuesta

**Síntomas:**
- `IndexError: list index out of range`
- `TypeError: 'NoneType' object is not subscriptable`

**Causa:**
Las respuestas de la API son listas anidadas sin schema estable.
Google puede cambiar la estructura sin aviso.

**Diagnóstico:**
```python
# 1. Activar debug y capturar la respuesta raw
# 2. Comparar la estructura esperada vs la real
# 3. Ajustar los índices en el service layer

# Ejemplo: si result[4] antes tenía timestamps y ahora es None,
# el código que hace result[4][0] va a fallar con IndexError
```

### Rate limiting

**Síntomas:**
- `HTTPStatusError: 429 Too Many Requests`
- Respuestas lentas seguidas de errores

**Info:**
- Free tier: ~50 queries/día
- El retry automático maneja 429 con backoff exponencial
- Si persiste: esperar 24h o usar cuenta Plus

## Paso 3: Herramientas de debug

### Ver request/response completo

```python
# En core/base.py, _call_rpc() loguea todo con logger.debug():
# - URL con parámetros
# - Request body decodificado (CSRF redactado)
# - Response status
# - Response data (parsed)
```

### Verificar estado de autenticación

```bash
# CLI
nlm login --check
nlm doctor

# MCP tool
refresh_auth()  # Recarga tokens
```

### Probar un RPC manualmente

```python
# Para debug rápido (NO en producción):
from notebooklm_tools.core.client import NotebookLMClient
from notebooklm_tools.core.auth import load_cached_tokens

tokens = load_cached_tokens()
client = NotebookLMClient(cookies=tokens.cookies)

# Llamada directa al RPC
result = client._call_rpc("wXbhsf", [None, 100])  # list_notebooks
print(result)
```

## Errores comunes y soluciones rápidas

| Error | Causa probable | Solución |
|-------|---------------|----------|
| 401/403 en primera llamada | Cookies expiradas | `nlm login` |
| 401 intermitente | CSRF expirado | Auto-recovery (esperar) |
| Respuesta vacía | RPC ID o params incorrectos | Verificar con `--debug` |
| IndexError en parsing | API cambió estructura | Comparar raw response |
| 429 Too Many Requests | Rate limit | Esperar 24h |
| `accounts.google.com` redirect | Sesión de Google expirada | `nlm login` |
| `NOTEBOOKLM_BL` mismatch | Frontend version cambió | Actualizar BL string |

## Actualizar el BL string

Si la API empieza a fallar sin razón obvia, puede ser que Google actualizó el frontend.

1. Abrir Chrome DevTools en notebooklm.google.com
2. Buscar cualquier request a `batchexecute`
3. En la URL, copiar el valor del parámetro `bl=`
4. Actualizar en `core/base.py:395` y `core/conversation.py:168`
5. O usar la env var `NOTEBOOKLM_BL=nuevo_valor`
