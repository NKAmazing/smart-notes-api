# Smart Notes API

API REST con **FastAPI** que analiza texto libre de una nota y devuelve un análisis estructurado: **resumen**, **puntos clave**, **tono** y qué **proveedor LLM** procesó la petición.

Los modelos se integran de forma **pluggable** (Groq, OpenAI, Gemini) mediante un único flujo de negocio y validación con **Pydantic**.

---

## Stack tecnológico

| Componente | Uso |
|------------|-----|
| **Python 3.10+** (recomendado; 3.9 puede funcionar con advertencias de dependencias) | Lenguaje |
| **FastAPI** | Framework HTTP, validación de entrada/salida, OpenAPI/Swagger |
| **Uvicorn** | Servidor ASGI |
| **Pydantic v2** | Esquemas `AnalyzeRequest` / `AnalyzeResponse` |
| **python-dotenv** | Carga de variables desde `.env` al arrancar |
| **openai** (SDK oficial) | Cliente **OpenAI** y proveedores **compatibles con la API de OpenAI** (p. ej. **Groq** vía `base_url`) |
| **google-genai** | Cliente **Google Gemini** (API de desarrollador) |

---

## Estructura del proyecto

```
smart-notes-api/
├── app/
│   ├── main.py                 # App FastAPI, carga de .env
│   ├── exceptions.py           # AnalysisError (errores de negocio → HTTP)
│   ├── routers/
│   │   └── notes.py            # POST /analyze
│   ├── schemas/
│   │   └── notes.py            # Modelos Pydantic de request/response
│   └── services/
│       ├── notes_service.py    # Orquesta analyze_note → analyze_text
│       └── llm_provider.py     # Proveedores LLM, prompt, fallback
├── requirements.txt
├── LICENSE.md
└── README.md
```

---

## Configuración rápida

### 1. Entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
```

### 2. Dependencias

```bash
pip install -r requirements.txt
```

### 3. Variables de entorno

Copiá `app/.env.example` a `app/.env` (o usá un `.env` en la raíz del repo) y completá las claves que vayas a usar.

Al iniciar, `app/main.py` carga en orden:

1. `app/.env`
2. `.env` en la raíz del proyecto

Las variables no definidas en el sistema se leen desde ahí.

### 4. Arranque

```bash
uvicorn app.main:app --reload
```

API base: `http://127.0.0.1:8000`

---

## Proveedores LLM y variables

El comportamiento central está en `app/services/llm_provider.py`.

### Selección de proveedor

| Variable | Valores | Por defecto |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq`, `openai`, `gemini` | `groq` |
| `LLM_FALLBACK_ENABLED` | `true` / `false` (y equivalentes `1`, `yes`, `on`) | `true` |

- **`LLM_PROVIDER`** define qué backend se intenta **primero**.
- Si **`LLM_FALLBACK_ENABLED=true`**, ante un fallo (error de API, cuota, etc.) se prueban **otros proveedores** en orden fijo: **groq → openai → gemini**, pero **solo si existe API key** para ese proveedor. El campo **`llm_provider`** en la respuesta indica cuál respondió con éxito (útil si hubo fallback).

### Claves y modelos por proveedor

| Proveedor | Variables | Modelo por defecto (si no definís otro) |
|-----------|-----------|----------------------------------------|
| **Groq** | `GROQ_API_KEY`, opcional `GROQ_MODEL` | `llama-3.3-70b-versatile` |
| **OpenAI** | `OPENAI_API_KEY`, opcional `OPENAI_MODEL` | `gpt-4o-mini` |
| **Gemini** | `GEMINI_API_KEY` o `GOOGLE_API_KEY`, opcional `GEMINI_MODEL` | `gemini-2.0-flash` |

- **Groq**: clave en [console.groq.com/keys](https://console.groq.com/keys). El cliente usa la API compatible con OpenAI con `base_url` fija: `https://api.groq.com/openai/v1` (no hace falta ponerla en el `.env`).
- **OpenAI**: clave en [platform.openai.com](https://platform.openai.com).
- **Gemini**: clave en [Google AI Studio](https://aistudio.google.com/apikey); SDK: `google-genai`.

Si ningún proveedor tiene clave configurada, la API responde con error indicando que falta configuración.

---

## Cómo funciona el cliente LLM (resumen técnico)

1. **`analyze_text(text)`** (`llm_provider.py`) elige proveedor según `LLM_PROVIDER` y aplica fallback opcional.
2. **OpenAI y Groq** comparten la misma ruta: cliente **`OpenAI`** del SDK oficial; Groq solo cambia `api_key` y `base_url`.
3. **Gemini** usa el cliente **`google.genai`** (`genai.Client`), `generate_content` con `response_mime_type="application/json"` y `system_instruction` con el mismo texto de sistema que los demás.
4. Se pide al modelo salida **solo JSON** con campos fijos (ver prompt abajo). Donde el proveedor lo permite, se usa **`response_format: { "type": "json_object" }`** (OpenAI-compatible).
5. El JSON se parsea; se valida contra un modelo interno `_LLMJsonOutput` (summary, key_points, tone) y luego se arma **`AnalyzeResponse`** añadiendo **`llm_provider`** con el id del backend que respondió.

Los errores de proveedor se encapsulan en **`AnalysisError`** (`app/exceptions.py`) con `status_code` y `message`; el router los convierte en **`HTTPException`** para el cliente HTTP.

---

## Prompt del sistema (proveedor)

El prompt vive en **`SYSTEM_PROMPT`** dentro de `llm_provider.py`. Pide explícitamente un **único objeto JSON** sin markdown, con:

- `summary` (string)
- `key_points` (array de strings)
- `tone` (string)

Para modificar el comportamiento del análisis, editá ese bloque (y, si cambiás la forma del JSON, actualizá los esquemas Pydantic en consecuencia).

---

## Esquemas (Pydantic)

Definidos en `app/schemas/notes.py` (usados en Swagger/ReDoc y en validación):

| Modelo | Rol |
|--------|-----|
| **`AnalyzeRequest`** | Entrada: `text` (string, mínimo 1 carácter). |
| **`AnalyzeResponse`** | Salida: `summary`, `key_points`, `tone`, **`llm_provider`** (identificador del backend: p. ej. `groq`, `openai`, `gemini`). |

El router **no** cambia: sigue devolviendo `AnalyzeResponse` en `POST /analyze`.

---

## API HTTP

### `GET /`

Comprueba que el servicio está arriba.

**Respuesta ejemplo:**

```json
{
  "status": "ok",
  "message": "Smart Notes API is running."
}
```

### `POST /analyze`

**Cuerpo:**

```json
{
  "text": "Hoy la reunión de equipo fue productiva; definimos prioridades para el trimestre."
}
```

**Respuesta ejemplo (forma actual):**

```json
{
  "summary": "…",
  "key_points": ["…", "…"],
  "tone": "neutral",
  "llm_provider": "groq"
}
```

Errores habituales: `401` / `429` / `502` / `503` / `504` según autenticación, límites, fallos del proveedor o configuración ausente. El cuerpo suele incluir `detail` con un mensaje legible.

---

## Documentación interactiva (OpenAPI)

| Interfaz | URL |
|----------|-----|
| Swagger UI | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| ReDoc | [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc) |

---

## Billing y límites (expectativas realistas)

Ningún proveedor garantiza uso ilimitado gratis de por vida; las políticas cambian. En la práctica:

- **Groq**, **Google AI (Gemini)** y **OpenAI** suelen ofrecer **capas gratuitas o de prueba** con **límites** (por minuto, por día, por proyecto).
- Mensajes del tipo **rate limit** o **quota exceeded** suelen indicar que tocó el techo del plan gratuito, que hace falta esperar, o que el proyecto pide **habilitar facturación** para subir cupos (depende del proveedor y de la cuenta).
- Para **aprender e integrar** no es obligatorio pagar; para **carga real o producción** conviene revisar en cada consola: **Billing**, **Quotas** y **Usage**.

Este repositorio no gestiona pagos: solo consume APIs con las claves que configures.

---

## Licencia

El código se publica bajo la **licencia MIT**. Ver **[LICENSE.md](./LICENSE.md)**.

---

## Ideas para seguir

- Autenticación (API key propia de tu backend, JWT, etc.)
- Persistencia de notas en base de datos
- Tests automatizados (pytest) con respuestas mockeadas del LLM
- Despliegue (Docker, Railway, Fly.io, etc.)
