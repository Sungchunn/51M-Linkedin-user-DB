# Negative Spaces Programming Philosophy

## What Are Negative Spaces?

In art, **negative space** is the space around and between the subject(s) of an image. In programming, **negative spaces** are the explicit boundaries, contracts, and invariants that define what **should NOT happen**.

By making invalid states **unrepresentable** and impossible conditions **immediately detectable**, bugs become obvious at the point of introduction rather than manifesting later as mysterious failures.

---

## Core Philosophy

### Traditional Debugging
```
Bug introduced → Silent propagation → Mysterious failure later → Hours of debugging
```

### Negative Spaces Debugging
```
Bug introduced → Immediate violation → Clear error at source → Minutes to fix
```

---

## The 10 Commandments of Negative Spaces

### 1. Make Impossible States Unrepresentable

**Bad**: Using strings for everything
```python
def process_status(status: str):
    if status == "pending":
        # ...
    elif status == "complete":
        # ...
    # What if status is "pendign" (typo)?
```

**Good**: Use enums
```python
from enum import Enum

class Status(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"

def process_status(status: Status):
    # Impossible to pass invalid status
    if status == Status.PENDING:
        # ...
```

---

### 2. Validate at Boundaries

**Bad**: Assume inputs are valid
```python
def embed_text(text: str) -> List[float]:
    return openai.embed(text)  # What if text is None? Empty? 1M chars?
```

**Good**: Guard at entry
```python
MAX_TEXT_LENGTH = 8000

def embed_text(text: str) -> List[float]:
    # NEGATIVE SPACE: Text must exist and be within bounds
    if text is None:
        raise ValueError("BOUNDARY VIOLATION: text cannot be None")

    if not isinstance(text, str):
        raise TypeError(f"BOUNDARY VIOLATION: text must be str, got {type(text)}")

    if len(text) == 0:
        raise ValueError("BOUNDARY VIOLATION: text cannot be empty")

    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(
            f"BOUNDARY VIOLATION: text length {len(text)} exceeds max {MAX_TEXT_LENGTH}"
        )

    return openai.embed(text)
```

---

### 3. Assert Invariants

**Bad**: Hope calculations are correct
```python
def quality_score(row: dict) -> float:
    score = 0.0
    score += 0.3 if row.get('name') else 0
    score += 0.3 if row.get('username') else 0
    score += 0.2 if row.get('title') else 0
    score += 0.2 if row.get('industry') else 0
    return score
```

**Good**: Assert post-conditions
```python
def quality_score(row: dict) -> float:
    """Calculate quality score. INVARIANT: result must be in [0.0, 1.0]"""
    score = 0.0
    score += 0.3 if row.get('name') else 0
    score += 0.3 if row.get('username') else 0
    score += 0.2 if row.get('title') else 0
    score += 0.2 if row.get('industry') else 0

    # INVARIANT CHECK
    if not (0.0 <= score <= 1.0):
        raise AssertionError(
            f"INVARIANT VIOLATION: quality_score={score} outside [0.0, 1.0]. "
            f"This indicates a logic error in the scoring calculation. "
            f"Row: {row}"
        )

    return score
```

---

### 4. Use Sentinel Values for Uninitialized State

**Bad**: None could mean uninitialized or intentionally null
```python
class DatabaseConnection:
    def __init__(self):
        self.conn = None  # Ambiguous: not initialized or connection failed?

    def query(self, sql):
        return self.conn.execute(sql)  # May crash with AttributeError
```

**Good**: Explicit sentinel
```python
UNINITIALIZED = object()

class DatabaseConnection:
    def __init__(self):
        self.conn = UNINITIALIZED

    def connect(self, dsn: str):
        self.conn = psycopg.connect(dsn)

    def query(self, sql: str):
        if self.conn is UNINITIALIZED:
            raise RuntimeError(
                "NEGATIVE SPACE VIOLATION: DatabaseConnection not initialized. "
                "Call .connect() before .query()"
            )
        return self.conn.execute(sql)
```

---

### 5. Fail Fast with Context

**Bad**: Silent failures or generic errors
```python
def load_config(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}  # Silent failure
```

**Good**: Fail loudly with context
```python
class ConfigLoadError(Exception):
    """Raised when configuration cannot be loaded"""
    pass

def load_config(path: str) -> dict:
    """Load config from JSON file. MUST exist and be valid JSON."""
    if not os.path.exists(path):
        raise ConfigLoadError(
            f"NEGATIVE SPACE VIOLATION: Config file not found at {path}. "
            f"Current working directory: {os.getcwd()}. "
            f"Did you forget to create .env?"
        )

    try:
        with open(path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigLoadError(
            f"NEGATIVE SPACE VIOLATION: Config file {path} is not valid JSON. "
            f"Error at line {e.lineno}, column {e.colno}: {e.msg}"
        ) from e

    # Validate required keys
    required = ['database', 'api_key']
    missing = [k for k in required if k not in config]
    if missing:
        raise ConfigLoadError(
            f"NEGATIVE SPACE VIOLATION: Config missing required keys: {missing}. "
            f"Found keys: {list(config.keys())}"
        )

    return config
```

---

### 6. Type Contracts with Runtime Validation

**Bad**: Type hints without enforcement
```python
def batch_records(records: List[dict], batch_size: int):
    # Crashes if records is None or batch_size is negative
    for i in range(0, len(records), batch_size):
        yield records[i:i+batch_size]
```

**Good**: Pydantic models or explicit validation
```python
from typing import List, Iterator
from pydantic import BaseModel, validator

class BatchConfig(BaseModel):
    records: List[dict]
    batch_size: int

    @validator('records')
    def records_not_empty(cls, v):
        if len(v) == 0:
            raise ValueError("NEGATIVE SPACE: records cannot be empty")
        return v

    @validator('batch_size')
    def batch_size_positive(cls, v):
        if v <= 0:
            raise ValueError(f"NEGATIVE SPACE: batch_size must be >0, got {v}")
        return v

def batch_records(config: BatchConfig) -> Iterator[List[dict]]:
    """Batch records. Type contract ensures valid inputs."""
    for i in range(0, len(config.records), config.batch_size):
        batch = config.records[i:i+config.batch_size]

        # POST-CONDITION: Batch cannot be empty
        assert len(batch) > 0, "INVARIANT VIOLATION: Empty batch generated"

        yield batch
```

---

### 7. Database Constraints as Negative Spaces

**Bad**: Relying on application logic only
```python
# No DB constraints, invalid data can slip in
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email TEXT,
  age INT
);
```

**Good**: DB enforces invariants
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- NEGATIVE SPACE: Email must exist and be valid format
  email TEXT NOT NULL CHECK (email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'),

  -- NEGATIVE SPACE: Age must be realistic
  age INT NOT NULL CHECK (age >= 0 AND age <= 150),

  -- NEGATIVE SPACE: Created timestamp cannot be in future
  created_at TIMESTAMPTZ DEFAULT NOW() CHECK (created_at <= NOW()),

  -- UNIQUE constraint prevents duplicates
  CONSTRAINT unique_email UNIQUE (email)
);

-- Index on email for lookups
CREATE UNIQUE INDEX idx_users_email ON users(email);
```

---

### 8. Structured Logging with Context

**Bad**: Print statements
```python
def process_row(row):
    print(f"Processing {row}")  # No context, hard to search
    # ...
```

**Good**: Structured logging with levels
```python
import logging
import json

logger = logging.getLogger(__name__)

def process_row(row: dict, row_number: int):
    logger.info(
        "Processing row",
        extra={
            'row_number': row_number,
            'row_id': row.get('id'),
            'has_email': bool(row.get('email'))
        }
    )

    # NEGATIVE SPACE: Required fields must exist
    required = ['id', 'name', 'email']
    missing = [f for f in required if not row.get(f)]

    if missing:
        logger.error(
            "NEGATIVE SPACE VIOLATION: Missing required fields",
            extra={
                'row_number': row_number,
                'row_id': row.get('id'),
                'missing_fields': missing,
                'available_fields': list(row.keys())
            }
        )
        raise ValueError(f"Row {row_number} missing fields: {missing}")

    # ... process row
```

---

### 9. Return Type Guarantees

**Bad**: Ambiguous return values
```python
def fetch_user(user_id: str):
    # Returns dict if found, None if not found, or raises on DB error
    # Caller doesn't know what to expect
    pass
```

**Good**: Explicit return types with guarantees
```python
from typing import Optional
from dataclasses import dataclass

@dataclass
class User:
    id: str
    name: str
    email: str

class UserNotFoundError(Exception):
    """Raised when user does not exist"""
    pass

class DatabaseError(Exception):
    """Raised when database operation fails"""
    pass

def fetch_user(user_id: str) -> User:
    """
    Fetch user by ID.

    NEGATIVE SPACE CONTRACT:
    - Returns User if found
    - Raises UserNotFoundError if not found
    - Raises DatabaseError on DB failure
    - NEVER returns None (type system enforces this)
    """
    if not user_id or user_id.strip() == '':
        raise ValueError("BOUNDARY VIOLATION: user_id cannot be empty")

    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, email FROM users WHERE id = %s",
                (user_id,)
            ).fetchone()

            if row is None:
                raise UserNotFoundError(
                    f"NEGATIVE SPACE: User {user_id} not found. "
                    f"This is not an error if user was deleted."
                )

            return User(**row)

    except psycopg.Error as e:
        raise DatabaseError(
            f"NEGATIVE SPACE: Database error fetching user {user_id}: {e}"
        ) from e
```

---

### 10. Pre/Post Condition Contracts

**Bad**: No contract documentation
```python
def divide(a, b):
    return a / b  # What if b is 0?
```

**Good**: Explicit contracts
```python
def divide(numerator: float, denominator: float) -> float:
    """
    Divide numerator by denominator.

    PRE-CONDITIONS (NEGATIVE SPACES):
    - numerator must be finite
    - denominator must be non-zero and finite

    POST-CONDITIONS (NEGATIVE SPACES):
    - result must be finite (not NaN or Inf)

    Raises:
        ValueError: If denominator is zero
        ValueError: If inputs are not finite
    """
    # PRE-CONDITION: Inputs must be finite
    if not math.isfinite(numerator):
        raise ValueError(
            f"PRE-CONDITION VIOLATION: numerator={numerator} is not finite"
        )

    if not math.isfinite(denominator):
        raise ValueError(
            f"PRE-CONDITION VIOLATION: denominator={denominator} is not finite"
        )

    # PRE-CONDITION: Denominator cannot be zero
    if denominator == 0:
        raise ValueError(
            f"PRE-CONDITION VIOLATION: Cannot divide by zero. "
            f"numerator={numerator}, denominator={denominator}"
        )

    result = numerator / denominator

    # POST-CONDITION: Result must be finite
    if not math.isfinite(result):
        raise AssertionError(
            f"POST-CONDITION VIOLATION: result={result} is not finite. "
            f"This indicates a logic error. "
            f"Inputs: numerator={numerator}, denominator={denominator}"
        )

    return result
```

---

## Practical Examples for This Project

### Example 1: Embedding Generation

```python
# data-pipeline/embeddings/generate.py

import logging
from typing import List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Sentinel for uninitialized client
UNINITIALIZED = object()

# Constants define negative space boundaries
MAX_TEXT_LENGTH = 8000
MIN_QUALITY_SCORE = 0.7
EMBEDDING_DIMENSION = 1536
MAX_BATCH_SIZE = 100

@dataclass
class EmbeddingConfig:
    """Configuration with built-in validation"""
    batch_size: int = 100
    max_text_len: int = MAX_TEXT_LENGTH
    min_quality: float = MIN_QUALITY_SCORE

    def __post_init__(self):
        # NEGATIVE SPACE: Batch size must be reasonable
        if not (1 <= self.batch_size <= MAX_BATCH_SIZE):
            raise ValueError(
                f"NEGATIVE SPACE: batch_size={self.batch_size} outside [1, {MAX_BATCH_SIZE}]"
            )

        # NEGATIVE SPACE: Quality threshold must be [0, 1]
        if not (0.0 <= self.min_quality <= 1.0):
            raise ValueError(
                f"NEGATIVE SPACE: min_quality={self.min_quality} outside [0.0, 1.0]"
            )

class EmbeddingService:
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._client = UNINITIALIZED

    def initialize(self, api_key: str):
        """Initialize embedding client. MUST be called before embed()."""
        if not api_key or api_key.strip() == '':
            raise ValueError("NEGATIVE SPACE: api_key cannot be empty")

        # Initialize client
        import openai
        self._client = openai.Client(api_key=api_key)

        logger.info("EmbeddingService initialized", extra={'config': self.config})

    def _get_client(self):
        """Get client with initialization check."""
        if self._client is UNINITIALIZED:
            raise RuntimeError(
                "NEGATIVE SPACE VIOLATION: EmbeddingService not initialized. "
                "Call .initialize() before .embed()"
            )
        return self._client

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for texts.

        PRE-CONDITIONS:
        - Service must be initialized
        - texts must not be empty
        - Each text must be within max length

        POST-CONDITIONS:
        - Returns exactly len(texts) embeddings
        - Each embedding is exactly EMBEDDING_DIMENSION floats

        Raises:
            RuntimeError: If service not initialized
            ValueError: If texts violate constraints
        """
        client = self._get_client()

        # PRE-CONDITION: texts not empty
        if not texts:
            raise ValueError("NEGATIVE SPACE: texts list cannot be empty")

        # PRE-CONDITION: Validate each text
        for i, text in enumerate(texts):
            if not isinstance(text, str):
                raise TypeError(
                    f"NEGATIVE SPACE: texts[{i}] is {type(text)}, expected str"
                )

            if len(text) == 0:
                raise ValueError(
                    f"NEGATIVE SPACE: texts[{i}] is empty string"
                )

            if len(text) > self.config.max_text_len:
                raise ValueError(
                    f"NEGATIVE SPACE: texts[{i}] length {len(text)} exceeds "
                    f"max {self.config.max_text_len}"
                )

        # Generate embeddings
        response = client.embeddings.create(
            input=texts,
            model="text-embedding-3-small"
        )

        embeddings = [item.embedding for item in response.data]

        # POST-CONDITION: Count matches
        if len(embeddings) != len(texts):
            raise AssertionError(
                f"POST-CONDITION VIOLATION: Generated {len(embeddings)} embeddings "
                f"for {len(texts)} texts"
            )

        # POST-CONDITION: Dimensions correct
        for i, emb in enumerate(embeddings):
            if len(emb) != EMBEDDING_DIMENSION:
                raise AssertionError(
                    f"POST-CONDITION VIOLATION: embeddings[{i}] has {len(emb)} dims, "
                    f"expected {EMBEDDING_DIMENSION}"
                )

            # POST-CONDITION: All values are numbers
            if not all(isinstance(x, (int, float)) for x in emb):
                raise AssertionError(
                    f"POST-CONDITION VIOLATION: embeddings[{i}] contains non-numeric values"
                )

        return embeddings


def quality_score(row: dict) -> float:
    """
    Calculate quality score for a row.

    NEGATIVE SPACE CONTRACT:
    - Result must be in [0.0, 1.0]
    - Missing fields contribute 0
    """
    score = 0.0
    score += 0.3 if row.get('full_name') else 0
    score += 0.3 if row.get('linkedin_username') else 0
    score += 0.2 if row.get('job_title') else 0
    score += 0.2 if row.get('industry') else 0

    # INVARIANT CHECK
    if not (0.0 <= score <= 1.0):
        logger.error(
            "INVARIANT VIOLATION: quality_score outside [0, 1]",
            extra={
                'score': score,
                'row_id': row.get('id'),
                'fields_present': list(row.keys())
            }
        )
        raise AssertionError(
            f"INVARIANT VIOLATION: quality_score={score} outside [0.0, 1.0]"
        )

    return score


def build_content(row: dict, max_length: int = MAX_TEXT_LENGTH) -> str:
    """
    Build content string from row using template.

    NEGATIVE SPACE CONTRACT:
    - Result never exceeds max_length
    - Result never empty (at minimum returns "Professional: ")
    """
    def clean(value) -> str:
        """Clean field value. NEGATIVE SPACE: Returns empty string for None."""
        if value is None:
            return ""
        return " ".join(str(value).split())  # Normalize whitespace

    # Build from template
    content = (
        f"Professional: {clean(row.get('job_title'))} "
        f"at {clean(row.get('company_name'))} | "
        f"Industry: {clean(row.get('industry'))} | "
        f"Location: {clean(row.get('location'))} | "
        f"Skills: {', '.join(row.get('skills', []))}"
    )

    # Truncate to max length
    if len(content) > max_length:
        content = content[:max_length]
        logger.warning(
            "Content truncated to max_length",
            extra={
                'row_id': row.get('id'),
                'original_length': len(content),
                'max_length': max_length
            }
        )

    # POST-CONDITION: Length check
    if len(content) > max_length:
        raise AssertionError(
            f"POST-CONDITION VIOLATION: content length {len(content)} exceeds "
            f"max {max_length}"
        )

    # POST-CONDITION: Not empty
    if len(content) == 0:
        raise AssertionError(
            f"POST-CONDITION VIOLATION: content is empty for row {row.get('id')}"
        )

    return content


def should_embed(row: dict, min_quality: float = MIN_QUALITY_SCORE) -> bool:
    """
    Determine if row should be embedded.

    NEGATIVE SPACE CONTRACT:
    - Returns True only if quality >= min_quality
    - Required fields must exist
    """
    # NEGATIVE SPACE: Must have linkedin_username (primary key)
    if not row.get('linkedin_username'):
        logger.debug(
            "Skipping row without linkedin_username",
            extra={'row_id': row.get('id')}
        )
        return False

    score = quality_score(row)

    if score < min_quality:
        logger.debug(
            "Skipping row below quality threshold",
            extra={
                'row_id': row.get('id'),
                'quality_score': score,
                'min_quality': min_quality
            }
        )
        return False

    return True
```

---

### Example 2: Database Operations

```python
# api/database.py

import asyncpg
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Sentinel
UNINITIALIZED = object()

# Pool configuration negative spaces
MIN_POOL_SIZE = 5
MAX_POOL_SIZE = 40
CONNECTION_TIMEOUT = 5.0

class DatabasePool:
    """
    Manages asyncpg connection pool with negative space contracts.
    """

    def __init__(self):
        self._pool = UNINITIALIZED

    async def initialize(
        self,
        user: str,
        password: str,
        database: str,
        host: str = "127.0.0.1",
        port: int = 5432,
        min_size: int = MIN_POOL_SIZE,
        max_size: int = MAX_POOL_SIZE
    ):
        """
        Initialize connection pool.

        NEGATIVE SPACE CONTRACTS:
        - min_size <= max_size
        - min_size >= 1
        - max_size <= 100 (PostgreSQL max_connections usually ~100)
        """
        # VALIDATION: Pool sizes
        if not (1 <= min_size <= max_size <= 100):
            raise ValueError(
                f"NEGATIVE SPACE: Invalid pool sizes. "
                f"min_size={min_size}, max_size={max_size}. "
                f"Must satisfy: 1 <= min_size <= max_size <= 100"
            )

        # VALIDATION: Required params
        if not all([user, password, database]):
            raise ValueError(
                "NEGATIVE SPACE: user, password, database cannot be empty"
            )

        try:
            self._pool = await asyncpg.create_pool(
                user=user,
                password=password,
                database=database,
                host=host,
                port=port,
                min_size=min_size,
                max_size=max_size,
                command_timeout=CONNECTION_TIMEOUT
            )

            logger.info(
                "Database pool initialized",
                extra={
                    'host': host,
                    'port': port,
                    'database': database,
                    'min_size': min_size,
                    'max_size': max_size
                }
            )

        except Exception as e:
            raise ConnectionError(
                f"NEGATIVE SPACE: Failed to initialize database pool: {e}"
            ) from e

    def get_pool(self) -> asyncpg.Pool:
        """
        Get pool. NEGATIVE SPACE: Must be initialized first.
        """
        if self._pool is UNINITIALIZED:
            raise RuntimeError(
                "NEGATIVE SPACE VIOLATION: DatabasePool not initialized. "
                "Call .initialize() first"
            )
        return self._pool

    async def close(self):
        """Close pool if initialized."""
        if self._pool is not UNINITIALIZED:
            await self._pool.close()
            logger.info("Database pool closed")


# Global instance
db_pool = DatabasePool()


async def get_connection():
    """
    Get database connection from pool.

    NEGATIVE SPACE: Pool must be initialized.
    """
    pool = db_pool.get_pool()  # Raises if not initialized
    return pool.acquire()
```

---

## Benefits of Negative Spaces

### 1. **Bugs Surface Immediately**
Instead of silent corruption, violations trigger errors at the source.

### 2. **Stack Traces Point to Root Cause**
Error messages include context, making debugging trivial.

### 3. **Self-Documenting Code**
Contracts and invariants document expected behavior.

### 4. **Prevents Regression**
Once a negative space is defined, it's enforced forever.

### 5. **Easier Testing**
Test cases naturally align with boundary conditions.

### 6. **Confident Refactoring**
Violations alert you immediately if refactoring breaks contracts.

---

## Anti-Patterns to Avoid

### ❌ Over-Assertion
```python
# Too granular - slows down code
def add(a, b):
    assert isinstance(a, int), "a must be int"
    assert isinstance(b, int), "b must be int"
    assert a >= 0, "a must be non-negative"
    assert b >= 0, "b must be non-negative"
    result = a + b
    assert result >= a, "result must be >= a"
    assert result >= b, "result must be >= b"
    return result
```

**Better**: Use type hints and validate at boundaries only.

### ❌ Silent Exception Swallowing
```python
# Defeats the purpose
try:
    validate_input(data)
except ValidationError:
    pass  # BAD - violates fail-fast
```

**Better**: Log and re-raise or handle explicitly.

### ❌ Generic Error Messages
```python
raise ValueError("Invalid input")  # Not helpful
```

**Better**: Include context
```python
raise ValueError(
    f"NEGATIVE SPACE: Invalid input. Expected dict with keys {expected_keys}, "
    f"got {type(data)} with keys {list(data.keys()) if isinstance(data, dict) else 'N/A'}"
)
```

---

## Checklist for Implementing Negative Spaces

- [ ] All function inputs validated at entry
- [ ] Return types explicit and guaranteed
- [ ] Pre/post-conditions documented
- [ ] Invariants asserted in critical calculations
- [ ] Database constraints mirror application logic
- [ ] Enums used instead of magic strings
- [ ] Sentinel values for uninitialized state
- [ ] Structured logging with context
- [ ] Type hints everywhere
- [ ] Pydantic models for complex data
- [ ] Custom exceptions with context chains
- [ ] Bounds checking on all numeric operations
- [ ] Collection size limits enforced
- [ ] Timeout enforcement on external calls
- [ ] Resource cleanup in finally/context managers

---

## Conclusion

**Negative Spaces** transform debugging from archaeology (digging for clues) into navigation (following error breadcrumbs to the source).

By defining what **should not happen** as explicitly as what **should happen**, you create a system that **fails loudly and clearly** rather than silently and mysteriously.

**Remember**: The goal isn't to prevent all bugs (impossible), but to make bugs **immediately obvious** when they occur.

---

**Last Updated**: 2025-10-07
**Philosophy Status**: Core principle for INSIGHT project
