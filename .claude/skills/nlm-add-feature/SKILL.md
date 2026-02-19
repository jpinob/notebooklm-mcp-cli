---
name: nlm-add-feature
description: Workflow completo para añadir un nuevo feature/endpoint RPC al proyecto NotebookLM MCP+CLI. Activar cuando el usuario quiera implementar un nuevo tool MCP, nuevo comando CLI, nuevo endpoint de la API de NotebookLM, o añadir funcionalidad que toque múltiples capas. Ejemplos: "añade un nuevo tool", "implementa studio rename", "nuevo RPC endpoint", "agrega soporte para X feature de NotebookLM".
---

# Añadir un nuevo feature a NotebookLM MCP+CLI

Sigue estos pasos EN ORDEN. No saltes ninguno.

## Requisitos previos

- Tener el RPC ID y la estructura de parámetros del endpoint
- Si no los tienes, usa el agente `nlm-rpc-analyst` para analizar la captura de Chrome DevTools

## Checklist de implementación

### Paso 1: Documentar el RPC endpoint

- [ ] Añadir RPC ID → nombre en `src/notebooklm_tools/core/utils.py` (dict RPC_NAMES)
- [ ] Documentar parámetros y respuesta en `docs/API_REFERENCE.md`
- [ ] Si hay nuevas constantes (tipos, formatos), añadir CodeMapper en `core/constants.py`

### Paso 2: Core mixin (capa baja)

- [ ] Crear o editar el mixin correspondiente en `core/` (ej: `core/studio.py`)
- [ ] Añadir método que llame `self._call_rpc(RPC_ID, params)`
- [ ] Retornar datos RAW de la API (sin lógica de negocio)
- [ ] El mixin hereda de BaseClient

```python
# Ejemplo: core/studio.py
class StudioMixin(BaseClient):
    def rename_artifact(self, notebook_id: str, artifact_id: str, new_name: str) -> Any:
        params = [notebook_id, artifact_id, new_name]
        return self._call_rpc("NEW_RPC_ID", params)
```

### Paso 3: Service layer (lógica de negocio)

- [ ] Crear o editar función en `services/` (ej: `services/studio.py`)
- [ ] Definir TypedDict para el retorno
- [ ] Validar inputs y lanzar `ValidationError` si son inválidos
- [ ] Llamar al método del client
- [ ] Parsear/normalizar la respuesta raw → TypedDict
- [ ] Manejar errores con `ServiceError`/`NotFoundError`

```python
# Ejemplo: services/studio.py
class RenameResult(TypedDict):
    artifact_id: str
    new_name: str
    message: str

def rename_artifact(client: NotebookLMClient, notebook_id: str,
                    artifact_id: str, new_name: str) -> RenameResult:
    if not new_name.strip():
        raise ValidationError("Name cannot be empty", debug_code="EMPTY_NAME")

    try:
        result = client.rename_artifact(notebook_id, artifact_id, new_name)
        return RenameResult(
            artifact_id=artifact_id,
            new_name=new_name,
            message=f"Renamed artifact to '{new_name}'"
        )
    except Exception as e:
        raise ServiceError(f"Failed to rename artifact: {e}", debug_code="RENAME_FAILED")
```

### Paso 4: MCP tool (wrapper delgado)

- [ ] Crear o editar en `mcp/tools/` (ej: `mcp/tools/studio.py`)
- [ ] Usar decorador `@logged_tool()`
- [ ] Llamar `get_client()` y delegar a `services/`
- [ ] Retornar `{"status": "success"|"error", ...}`
- [ ] Catch `ServiceError` → `{"status": "error", "error": e.user_message}`

```python
@logged_tool()
def studio_rename(notebook_id: str, artifact_id: str, new_name: str) -> dict[str, Any]:
    """Rename a studio artifact."""
    try:
        client = get_client()
        result = studio_service.rename_artifact(client, notebook_id, artifact_id, new_name)
        return {"status": "success", **result}
    except ServiceError as e:
        return {"status": "error", "error": e.user_message}
```

### Paso 5: CLI command (wrapper delgado)

- [ ] Crear o editar en `cli/commands/` (ej: `cli/commands/studio.py`)
- [ ] Usar Typer para definir el comando
- [ ] Delegar a `services/`
- [ ] Catch `ServiceError` → print + `raise typer.Exit(1)`
- [ ] Usar formatters para output

### Paso 6: Tests

- [ ] Escribir tests en `tests/services/` (mock del client)
- [ ] Mínimo 3 tests: caso normal, edge case, caso de error
- [ ] Usar el skill `nlm-test-patterns` para el formato correcto
- [ ] Ejecutar con `uv run pytest tests/services/test_<module>.py -v`

### Paso 7: Documentación

- [ ] Añadir test case a `docs/MCP_CLI_TEST_PLAN.md`
- [ ] Si el tool necesita confirmación, documentarlo en CLAUDE.md

## Reglas inquebrantables

1. **cli/ y mcp/ NUNCA importan de core/** — siempre pasan por services/
2. **services/ retorna TypedDict** — nunca dict plano ni Any
3. **services/ lanza ServiceError** — nunca excepciones raw
4. **MCP tools retornan {"status": "success"|"error"}** — siempre
5. **Tests NUNCA usan credenciales reales** — siempre mocks
