---
name: nlm-security-check
description: Checklist de seguridad específico para el proyecto NotebookLM antes de commits. Activar antes de commitear cambios, después de modificar código de autenticación, cookies, o tokens, y durante revisiones de código. Ejemplos: "revisa seguridad antes del commit", "es seguro commitear esto?", "check de seguridad", "revisa auth changes".
---

# Security Check — NotebookLM MCP+CLI

Ejecuta este checklist ANTES de cada commit que toque auth, cookies, tokens, o logging.

## Quick Scan (ejecutar siempre)

### 1. Buscar credenciales expuestas

```bash
# En archivos staged para commit
git diff --cached --name-only | xargs grep -l "SID=\|HSID=\|SSID=\|__Secure-\|Bearer \|at=" 2>/dev/null

# En todo el src/
grep -rn "cookie.*=.*['\"].*[a-zA-Z0-9_-]{20}" src/ --include="*.py"
```

Si encuentras resultados: **STOP. No commitear.**

### 2. Verificar que no se loguean credenciales

```bash
# Buscar logging de datos sensibles
grep -rn "print.*cookie\|print.*token\|print.*csrf\|print.*session_id" src/ --include="*.py" -i
grep -rn "logger.*cookie\|logger.*token\|logger.*csrf" src/ --include="*.py" -i
```

Excepciones permitidas:
- `result["at"] = "(csrf_token)"` — esto es REDACCIÓN, está bien
- `console.print("Cookies: present")` — no expone valores, está bien
- `logger.info(f"Auth tokens cached to {path}")` — solo path, está bien

### 3. Verificar permisos de archivos auth

Si el cambio toca escritura de archivos de auth:

```python
# OBLIGATORIO después de escribir cookies/tokens a disco:
path.chmod(0o600)       # Para archivos
directory.chmod(0o700)  # Para directorios
```

Verificar en:
- `core/auth.py` — `save_tokens_to_cache()` y `AuthManager.save_profile()`
- Cualquier función nueva que escriba credenciales

### 4. Verificar .gitignore

Debe contener al menos:
- `cookies.txt`
- `.notebooklm*/`
- `*.log`
- `.env` / `.env.*`

### 5. Verificar que MCP responses no retornan credenciales

```python
# NUNCA retornar cookies o tokens en respuestas MCP
# BAD:
return {"status": "success", "cookies": cookie_dict}
return {"status": "success", "csrf_token": token}

# GOOD:
return {"status": "success", "message": "Saved 15 essential cookies."}
```

### 6. Verificar tests sin credenciales reales

```bash
# Buscar patrones de cookies reales en tests
grep -rn "SID=.*HSID=\|__Secure-.*PSID" tests/ --include="*.py"
```

## Deep Scan (cuando se toca código de auth)

### 7. Chrome CDP security

Si se modifica `utils/cdp.py`:
- [ ] `--remote-allow-origins` no debe ser `*` (ideal: `http://localhost:{port}`)
- [ ] Chrome profile directory tiene permisos restrictivos
- [ ] No se exponen puertos CDP más allá de lo necesario

### 8. HTTP client security

Si se modifica `core/base.py`:
- [ ] Cookies solo se envían a `.google.com` y `.googleusercontent.com`
- [ ] No se envían credenciales a dominios de terceros
- [ ] CSRF token incluido en requests (`at=` en body)
- [ ] Debug logging redacta el CSRF token (verificar `_decode_request_body`)

### 9. Environment variables

Si se añaden nuevas env vars:
- [ ] No contienen valores por defecto con credenciales
- [ ] Documentadas en CLAUDE.md o README.md
- [ ] `.env.example` actualizado si existe

## Resultado

```
SECURITY CHECK: [PASS / FAIL]
  Credenciales expuestas:  [OK / FOUND at file:line]
  Logging seguro:          [OK / LEAK at file:line]
  Permisos de archivo:     [OK / MISSING at file:line]
  .gitignore:              [OK / INCOMPLETE]
  MCP responses limpias:   [OK / LEAK at file:line]
  Tests sin credenciales:  [OK / FOUND at file:line]
```

Si algún check es FAIL: **NO commitear hasta corregir.**
