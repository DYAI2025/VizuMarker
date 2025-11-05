# VizuMarker Code Audit Report

**Date:** 2025-11-05
**Project:** VizuMarker - Automatic Marker Detection (LD-3.5)
**Auditor:** Claude Code

---

## Executive Summary

This audit identifies **25 issues** across critical, major, and minor categories in the VizuMarker codebase. **3 showstopper issues** require immediate attention before production deployment. The system architecture is sound, but several security vulnerabilities, missing dependencies, and code quality issues need resolution.

---

## Issue Categories

- **CRITICAL (Showstoppers):** 3 issues
- **MAJOR:** 8 issues
- **MINOR:** 14 issues

---

## CRITICAL ISSUES (Showstoppers)

### 🔴 CRITICAL-1: Missing PyJWT Dependency
**File:** `ld35_service/core/security.py:5`
**Severity:** CRITICAL - Application crashes on startup

**Description:**
The `security.py` module imports and uses `jwt` (PyJWT library) but this dependency is **NOT** listed in `pyproject.toml`. This will cause an `ImportError` when the authentication system is enabled.

```python
# ld35_service/core/security.py:5
import jwt  # ❌ PyJWT not in dependencies
```

**Impact:**
- Application fails to start when authentication is enabled
- Docker container build will fail
- All authenticated endpoints become unavailable

**Fix Required:**
Add to `pyproject.toml`:
```toml
[tool.poetry.dependencies]
PyJWT = "^2.8.0"
```

---

### 🔴 CRITICAL-2: Unsafe eval() Usage - Code Injection Vulnerability
**File:** `ld35_service/core/ld35_engine.py:748`
**Severity:** CRITICAL - Remote Code Execution Risk

**Description:**
The code uses Python's built-in `eval()` to evaluate activation expressions, which poses a **critical security vulnerability** allowing arbitrary code execution.

```python
# ld35_service/core/ld35_engine.py:748
def _evaluate_expression(self, expression: Optional[str], context: Dict[str, Any]) -> bool:
    if not expression:
        return True
    expr = expression.replace("&&", " and ").replace("||", " or ")
    safe_globals = {"__builtins__": {}}  # ⚠️ Not safe enough!
    try:
        return bool(eval(expr, safe_globals, context))  # ❌ DANGEROUS!
```

**Impact:**
- Malicious marker definitions could execute arbitrary Python code
- Potential for remote code execution
- Complete system compromise possible

**Attack Vector:**
A malicious `markers_canonical.ld35.json` with:
```json
{
  "activation": "__import__('os').system('rm -rf /')"
}
```

**Fix Required:**
Use the safer AST-based evaluation already implemented in `ld35_service/engine/sem_core.py:236-250`. The `eval_activation()` function there properly restricts operations.

---

### 🔴 CRITICAL-3: Missing __init__.py Files - Package Import Failures
**Files:**
- `ld35_service/__init__.py` (missing)
- `ld35_service/api/__init__.py` (missing)
- `ld35_service/api/v1/__init__.py` (missing)

**Severity:** CRITICAL - Import failures

**Description:**
Python packages require `__init__.py` files to be recognized as modules. Without these, relative imports will fail.

**Impact:**
- Cannot import modules using `from ld35_service.api.v1 import annotation`
- Docker builds may fail
- Tests will not run correctly

**Fix Required:**
Create empty `__init__.py` files in all package directories.

---

## MAJOR ISSUES

### 🟠 MAJOR-1: Deprecated datetime.utcnow() Usage
**File:** `ld35_service/core/security.py:53,55`
**Severity:** MAJOR - Will break in Python 3.12+

**Description:**
Using deprecated `datetime.utcnow()` which is removed in Python 3.12+.

```python
# security.py:53-55
expire = datetime.utcnow() + expires_delta  # ❌ Deprecated
```

**Impact:**
- Code will break when upgrading to Python 3.12+
- DeprecationWarning spam in logs

**Fix:**
```python
from datetime import datetime, timezone
expire = datetime.now(timezone.utc) + expires_delta
```

---

### 🟠 MAJOR-2: Race Condition in Batch Processing
**File:** `ld35_service/workers/annotation_tasks.py:95`
**Severity:** MAJOR - Performance degradation

**Description:**
The batch processing task calls `.delay().get()` which blocks the worker, defeating the purpose of async processing.

```python
# annotation_tasks.py:95
result = process_annotation_task.delay(doc_id, text, doc_options).get()  # ❌ Blocking!
```

**Impact:**
- Worker threads blocked waiting for subtasks
- Poor scalability
- Defeats Celery's async benefits

**Fix:**
Use Celery groups/chords for parallel batch processing:
```python
from celery import group
job = group(process_annotation_task.s(doc['id'], doc['text'], doc.get('options'))
            for doc in documents)
results = job.apply_async()
```

---

### 🟠 MAJOR-3: Insecure Default SECRET_KEY
**Files:**
- `ld35_service/core/security.py:12`
- `docker-compose.yml:13,36,52`

**Severity:** MAJOR - Security vulnerability

**Description:**
Default SECRET_KEY is hardcoded and used in production configurations.

```python
# security.py:12
SECRET_KEY = os.getenv("SECRET_KEY", "your-default-secret-key-change-in-production")
```

**Impact:**
- JWT tokens can be forged
- Session hijacking possible
- Complete authentication bypass

**Fix:**
- Remove default value entirely
- Add startup validation requiring SECRET_KEY in production
- Generate strong random key in deployment docs

---

### 🟠 MAJOR-4: Missing Input Validation
**File:** `ld35_service/api/v1/annotation.py:25-87`
**Severity:** MAJOR - DoS vulnerability

**Description:**
No length validation on text input. Users can submit unlimited text sizes causing memory exhaustion.

**Impact:**
- Out-of-memory crashes
- Denial of service attacks
- Worker process failures

**Fix:**
Add validation in AnnotationRequest schema:
```python
from pydantic import Field, validator

class AnnotationRequest(BaseModel):
    text: str = Field(..., max_length=10_000_000)  # 10MB text limit

    @validator('text')
    def validate_text_size(cls, v):
        if len(v.encode('utf-8')) > 10 * 1024 * 1024:
            raise ValueError("Text exceeds 10MB limit")
        return v
```

---

### 🟠 MAJOR-5: Annotation.copy() Method Missing
**File:** `ld35_service/utils/chunking.py:63`
**Severity:** MAJOR - Runtime crash

**Description:**
Code calls `ann.copy()` but Pydantic BaseModel doesn't have `copy()` method in v2.

```python
# chunking.py:63
new_ann = ann.copy()  # ❌ AttributeError in Pydantic v2
```

**Impact:**
- Crashes when processing chunked documents
- Large document processing completely broken

**Fix:**
```python
new_ann = ann.model_copy()  # Pydantic v2 method
```

---

### 🟠 MAJOR-6: Missing Resources Directory Handling
**Files:** `ld35_service/core/ld35_engine.py:61-89`, `ld35_service/engine/sem_core.py:74-81`
**Severity:** MAJOR - Silent failures

**Description:**
Code assumes `resources/` directory exists with marker definition files. No validation or helpful error messages when missing.

**Impact:**
- Engine returns empty results silently
- No annotations detected
- Confusing user experience

**Fix:**
Add validation in `__init__`:
```python
if not (self.resources_path / "markers_canonical.ld35.json").exists():
    raise FileNotFoundError(
        f"Required marker definitions not found at {self.resources_path}. "
        "Please ensure markers_canonical.ld35.json exists."
    )
```

---

### 🟠 MAJOR-7: CORS Configuration Issue
**File:** `ld35_service/main.py:21`
**Severity:** MAJOR - CORS failures

**Description:**
Using `allow_origin_regex` with potential None value causes middleware errors.

```python
# main.py:21
allow_origin_regex=settings.ALLOWED_ORIGIN_REGEX,  # Can be None
```

**Impact:**
- CORS middleware initialization failure
- API unusable from browsers

**Fix:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    **({"allow_origin_regex": settings.ALLOWED_ORIGIN_REGEX}
       if settings.ALLOWED_ORIGIN_REGEX else {})
)
```

---

### 🟠 MAJOR-8: Missing Error Propagation
**File:** `ld35_service/core/storage.py:33,45,58,71,82,94,109,120,131`
**Severity:** MAJOR - Silent data loss

**Description:**
Storage operations use `print()` for errors and return `False`, but callers don't check return values consistently.

**Impact:**
- Silent data loss
- Inconsistent state
- Hard to debug failures

**Fix:**
Raise exceptions instead of returning False:
```python
def save_original_text(self, doc_id: str, text: str) -> None:
    try:
        path = self.storage_path / "originals" / f"{doc_id}.txt"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
    except Exception as e:
        logger.error(f"Error saving original text: {e}")
        raise StorageError(f"Failed to save document {doc_id}") from e
```

---

## MINOR ISSUES

### 🟡 MINOR-1: Inconsistent Logging
**Files:** Multiple

**Description:**
Mix of `print()` statements and `logger` usage throughout codebase.

**Examples:**
- `storage.py:33,45,58,71,82,94,109,120,131` - uses `print()`
- `annotation_tasks.py:11,44,46,74,103` - uses `logger`

**Fix:** Standardize on logger everywhere.

---

### 🟡 MINOR-2: Missing Type Hints
**Files:** Multiple

**Description:**
Inconsistent type hinting, especially in return types.

**Examples:**
- `ld35_engine.py:170` - `_run_carl_engine` has no return type
- `chunking.py:49` - missing return type on `normalize_text`

**Fix:** Add comprehensive type hints for better IDE support and type checking.

---

### 🟡 MINOR-3: Magic Numbers Without Constants
**Files:** Multiple

**Description:**
Hardcoded values scattered throughout code.

**Examples:**
```python
# chunking.py:5
chunk_size: int = 12000  # Why 12000?

# annotation_tasks.py:42
annotations = process_ld35_annotations(normalized_text, options)  # What are defaults?

# sem_core.py:136
context_window: int = 10  # Magic number
```

**Fix:** Define constants with explanatory names.

---

### 🟡 MINOR-4: No API Rate Limiting
**File:** `ld35_service/main.py`

**Description:**
API endpoints have no rate limiting, enabling abuse.

**Fix:** Add rate limiting middleware using slowapi or similar.

---

### 🟡 MINOR-5: Missing Database Configuration
**File:** `pyproject.toml`

**Description:**
SQLAlchemy and Alembic are dependencies but no database configuration or migrations exist.

**Impact:** Dead code, wasted dependencies.

**Fix:** Either implement database storage or remove unused dependencies.

---

### 🟡 MINOR-6: No Health Check Dependencies
**File:** `ld35_service/main.py:36-38`

**Description:**
Health check doesn't verify Redis, Celery, or storage availability.

**Fix:**
```python
@app.get("/health")
def health_check():
    health = {"status": "healthy", "services": {}}

    # Check Redis
    try:
        celery_app.backend.client.ping()
        health["services"]["redis"] = "ok"
    except:
        health["services"]["redis"] = "down"
        health["status"] = "degraded"

    return health
```

---

### 🟡 MINOR-7: Incomplete BIO Tokenization
**File:** `ld35_service/workers/annotation_tasks.py:211-248`

**Description:**
BIO export uses naive whitespace tokenization instead of proper NLP tokenization.

**Impact:** Inaccurate token boundaries for non-whitespace languages.

---

### 🟡 MINOR-8: No Request ID Tracing
**Files:** All API endpoints

**Description:**
No request ID correlation for debugging across services.

**Fix:** Add request ID middleware.

---

### 🟡 MINOR-9: Missing Batch Annotation Options
**File:** `ld35_service/schemas/annotation.py:36-37`

**Description:**
`BatchAnnotationRequest` doesn't have a global `options` field, forcing per-document options.

---

### 🟡 MINOR-10: Hardcoded Family Colors
**File:** `frontend/public/index.html:89-95`

**Description:**
Color scheme is hardcoded in CSS, should be configurable.

---

### 🟡 MINOR-11: No Docker Health Checks
**File:** `docker-compose.yml`

**Description:**
Docker services lack health check configurations.

**Fix:**
```yaml
ld35-service:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

---

### 🟡 MINOR-12: Missing .env.example
**File:** `.env.example` (missing)

**Description:**
No example environment file for deployment guidance.

---

### 🟡 MINOR-13: No API Documentation
**Files:** API endpoints

**Description:**
Missing OpenAPI/Swagger descriptions and examples.

**Fix:** Add docstrings with FastAPI's OpenAPI integration.

---

### 🟡 MINOR-14: Unused Imports
**Files:** Multiple

**Description:**
Several unused imports detected.

**Examples:**
- `ld35_engine.py:174` - imports `json` twice
- `annotation.py:6` - imports `hashlib` but uses it inline

---

## Summary by Category

| Severity | Count | Must Fix for Production |
|----------|-------|------------------------|
| CRITICAL | 3 | ✅ Yes (Showstoppers) |
| MAJOR | 8 | ✅ Yes |
| MINOR | 14 | ⚠️ Recommended |
| **TOTAL** | **25** | **11 blocking issues** |

---

## Recommendations

### Immediate Actions (Pre-Production)
1. ✅ Fix all 3 CRITICAL issues
2. ✅ Fix MAJOR-1 through MAJOR-8
3. ✅ Add comprehensive test coverage
4. ✅ Security audit of authentication system
5. ✅ Load testing for memory limits

### Short-term Improvements
1. Address logging inconsistencies
2. Add rate limiting
3. Implement proper health checks
4. Add request tracing
5. Complete API documentation

### Long-term Enhancements
1. Remove unused dependencies (SQLAlchemy/Alembic or implement)
2. Add comprehensive monitoring
3. Implement caching layer
4. Add metrics/observability
5. Performance optimization

---

## Positive Aspects

✅ Well-structured modular architecture
✅ Good separation of concerns (API/Engine/Workers)
✅ Comprehensive Docker setup
✅ Pydantic schemas for validation
✅ Async processing with Celery
✅ Multi-format export support
✅ Safe AST-based eval in sem_core.py (good pattern)

---

**End of Audit Report**
