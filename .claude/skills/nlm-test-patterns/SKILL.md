---
name: nlm-test-patterns
description: Patrones de testing para el proyecto NotebookLM. Activar cuando se necesiten escribir tests, actualizar tests existentes, o entender la estructura de tests del proyecto. Ejemplos: "escribe tests para X", "añade tests al servicio", "cómo testear esto?", "patrón de test para mcp tools".
---

# Test Patterns — NotebookLM MCP+CLI

## Entorno

```bash
uv run pytest                                    # Todos los tests
uv run pytest tests/services/ -v                 # Solo servicios
uv run pytest tests/services/test_X.py::TestY -v # Test específico
uv run pytest -m "not e2e" -v                    # Sin tests e2e
```

## Patrón 1: Service Layer Tests (el más común)

Mockear el `NotebookLMClient` y testear la función del servicio.

```python
# tests/services/test_notebooks.py
import pytest
from unittest.mock import MagicMock
from notebooklm_tools.services.notebooks import list_notebooks
from notebooklm_tools.services.errors import ServiceError

@pytest.fixture
def mock_client():
    """Mock NotebookLMClient — el fixture más usado."""
    return MagicMock()


class TestListNotebooks:
    """Agrupar tests por función del servicio."""

    def test_returns_notebooks_with_count(self, mock_client):
        """Caso normal: la API retorna datos válidos."""
        mock_client.list_notebooks.return_value = [
            ["Test Notebook", [["src-1", "Source"]], "nb-123", None, [1700000000, 0]]
        ]
        result = list_notebooks(mock_client)

        assert result["count"] == 1
        assert result["notebooks"][0]["id"] == "nb-123"
        assert result["notebooks"][0]["title"] == "Test Notebook"

    def test_empty_list(self, mock_client):
        """Edge case: no hay notebooks."""
        mock_client.list_notebooks.return_value = []
        result = list_notebooks(mock_client)

        assert result["count"] == 0
        assert result["notebooks"] == []

    def test_api_error_raises_service_error(self, mock_client):
        """Caso de error: la API falla."""
        mock_client.list_notebooks.side_effect = RuntimeError("API failed")

        with pytest.raises(ServiceError):
            list_notebooks(mock_client)
```

### Reglas para service tests:
- Fixture `mock_client` = `MagicMock()` (simula NotebookLMClient)
- Configurar `mock_client.<method>.return_value` con datos que imiten la API
- Verificar que el retorno es TypedDict correcto (keys, types, values)
- Verificar que errores se convierten en `ServiceError`
- NUNCA usar credenciales reales

## Patrón 2: Core/Mixin Tests

Mockear la respuesta RPC y testear el parsing.

```python
# tests/core/test_notebooks.py
import pytest
from unittest.mock import patch, MagicMock
from notebooklm_tools.core.notebooks import NotebookMixin

@pytest.fixture
def mixin():
    """Mock del mixin — no hace HTTP real."""
    m = MagicMock(spec=NotebookMixin)
    m.list_notebooks = NotebookMixin.list_notebooks.__get__(m)
    return m

class TestListNotebooks:
    def test_calls_correct_rpc(self, mixin):
        """Verifica que se llama al RPC ID correcto."""
        mixin._call_rpc.return_value = [...]
        mixin.list_notebooks()
        mixin._call_rpc.assert_called_once()
        call_args = mixin._call_rpc.call_args
        assert call_args[0][0] == "wXbhsf"  # RPC ID for list_notebooks
```

## Patrón 3: Validation Tests

Testear que las validaciones del servicio funcionan.

```python
class TestAddSource:
    def test_invalid_source_type_raises_validation_error(self, mock_client):
        from notebooklm_tools.services.errors import ValidationError

        with pytest.raises(ValidationError, match="Invalid source type"):
            add_source(mock_client, "nb-123", source_type="invalid")

    def test_empty_url_raises_validation_error(self, mock_client):
        from notebooklm_tools.services.errors import ValidationError

        with pytest.raises(ValidationError, match="URL cannot be empty"):
            add_source(mock_client, "nb-123", source_type="url", url="")
```

## Patrón 4: Tests con confirm=True

Para operaciones destructivas que requieren confirmación.

```python
class TestDeleteNotebook:
    def test_delete_without_confirm_raises(self, mock_client):
        """Sin confirm=True, debe rechazar."""
        with pytest.raises(ValidationError, match="confirm"):
            delete_notebook(mock_client, "nb-123", confirm=False)

    def test_delete_with_confirm_succeeds(self, mock_client):
        """Con confirm=True, procede."""
        mock_client.delete_notebook.return_value = True
        result = delete_notebook(mock_client, "nb-123", confirm=True)
        assert result["deleted"] is True
```

## Mínimo por función

Cada función de servicio nueva DEBE tener al menos:
1. **Test de caso normal** — datos válidos, respuesta esperada
2. **Test de edge case** — lista vacía, datos mínimos, valores límite
3. **Test de error** — API falla → `ServiceError` raised

## Markers disponibles

```python
@pytest.mark.e2e          # Requiere autenticación live (NO ejecutar en CI)
@pytest.mark.integration  # Tests de CLI (más lentos)
```

## Datos de test

```python
# IDs de ejemplo para tests (NUNCA usar IDs reales)
MOCK_NOTEBOOK_ID = "nb-test-123"
MOCK_SOURCE_ID = "src-test-456"
MOCK_ARTIFACT_ID = "art-test-789"
MOCK_TASK_ID = "task-test-abc"
```
