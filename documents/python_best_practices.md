# Python Best Practices Guide

## Code Style and Formatting

### PEP 8 Standards
Follow Python Enhancement Proposal 8 (PEP 8) for consistent code style:

- **Indentation**: Use 4 spaces per indentation level
- **Line Length**: Keep lines under 79 characters (docstrings/comments: 72)
- **Imports**: One per line, grouped (standard library, third-party, local)
- **Naming Conventions**:
  - Variables/functions: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_CASE`
  - Private members: `_leading_underscore`

### Code Organization
```python
"""Module docstring."""

import os
import sys
from typing import List, Dict

# Constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30

# Classes
class DataProcessor:
    """Process and validate data."""

    def __init__(self, name: str):
        self.name = name

    def process(self, data: List[str]) -> Dict:
        """Process input data."""
        pass

# Functions
def main():
    """Entry point."""
    pass

if __name__ == "__main__":
    main()
```

## Type Hints and Documentation

### Type Annotations
Always use type hints for better code clarity:

```python
from typing import List, Optional, Tuple, Union

def calculate_mean(values: List[float]) -> float:
    """Calculate arithmetic mean."""
    return sum(values) / len(values)

def find_item(items: List[str], target: str) -> Optional[int]:
    """Find item index, return None if not found."""
    try:
        return items.index(target)
    except ValueError:
        return None

def process_data(data: Union[str, bytes]) -> Tuple[int, str]:
    """Process data and return count and result."""
    return len(data), str(data)
```

### Docstrings
Use comprehensive docstrings following Google style:

```python
def complex_function(param1: str, param2: int = 5) -> bool:
    """Brief description of function.

    Longer description explaining what the function does,
    including any important details or gotchas.

    Args:
        param1: Description of param1
        param2: Description of param2 (default: 5)

    Returns:
        Boolean indicating success status

    Raises:
        ValueError: When param1 is empty
        TypeError: When param2 is not an integer

    Example:
        >>> result = complex_function("test", 10)
        >>> print(result)
        True
    """
    if not param1:
        raise ValueError("param1 cannot be empty")
    if not isinstance(param2, int):
        raise TypeError("param2 must be integer")

    return len(param1) > param2
```

## Error Handling

### Exception Handling Best Practices
```python
# Good: Specific exception handling
try:
    with open("file.txt") as f:
        data = f.read()
except FileNotFoundError:
    print("File not found")
except IOError as e:
    print(f"IO error: {e}")
else:
    # Execute if no exception
    process_data(data)
finally:
    # Always executes
    cleanup()

# Bad: Catching all exceptions
try:
    dangerous_operation()
except:  # Don't do this!
    pass
```

### Context Managers
Use context managers for resource management:

```python
# File handling
with open("data.txt") as f:
    content = f.read()

# Database connections
from contextlib import contextmanager

@contextmanager
def database_connection(url):
    db = connect(url)
    try:
        yield db
    finally:
        db.close()

# Usage
with database_connection("postgresql://...") as db:
    results = db.query("SELECT * FROM users")
```

## Performance Optimization

### Avoid Common Pitfalls
```python
# Bad: Modifying list while iterating
for item in my_list:
    if condition(item):
        my_list.remove(item)  # Don't do this!

# Good: Create new list
my_list = [item for item in my_list if not condition(item)]

# Bad: Creating unnecessary objects
for i in range(n):
    result = []
    result.append(i)
    process(result)

# Good: Reuse objects
result = []
for i in range(n):
    result.clear()
    result.append(i)
    process(result)
```

### Efficient Data Structures
```python
# Use sets for membership testing (O(1))
if item in my_set:  # Fast
    pass

# Avoid with lists (O(n))
if item in my_list:  # Slow
    pass

# Use defaultdict to avoid key checking
from collections import defaultdict

counts = defaultdict(int)
for item in data:
    counts[item] += 1

# Use Counter for counting
from collections import Counter
counts = Counter(data)
```

### Generator Functions
```python
# Bad: Load everything into memory
def get_all_numbers(n):
    result = []
    for i in range(n):
        result.append(i ** 2)
    return result

# Good: Use generator
def get_numbers_generator(n):
    for i in range(n):
        yield i ** 2

# Usage
for num in get_numbers_generator(1000000):
    process(num)
```

## Testing and Debugging

### Unit Testing
```python
import unittest

class TestCalculator(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.calc = Calculator()

    def test_addition(self):
        """Test addition operation."""
        self.assertEqual(self.calc.add(2, 3), 5)

    def test_division_by_zero(self):
        """Test division by zero raises error."""
        with self.assertRaises(ValueError):
            self.calc.divide(10, 0)

    def tearDown(self):
        """Clean up after tests."""
        self.calc = None

if __name__ == "__main__":
    unittest.main()
```

### Logging Best Practices
```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Usage
logger.debug("Debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical issue")

# Logging exceptions
try:
    risky_operation()
except Exception:
    logger.exception("Error in risky_operation")
```

## Concurrency and Async

### Threading for I/O Operations
```python
from concurrent.futures import ThreadPoolExecutor
import requests

def fetch_url(url):
    response = requests.get(url)
    return response.text

urls = ["http://example.com", "http://example.org"]

with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(fetch_url, urls))
```

### Async/Await Pattern
```python
import asyncio

async def async_operation(url):
    """Perform async HTTP request."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

async def main():
    """Run multiple async operations."""
    urls = ["http://example.com", "http://example.org"]
    tasks = [async_operation(url) for url in urls]
    results = await asyncio.gather(*tasks)

asyncio.run(main())
```

## Security Best Practices

### Input Validation
```python
import re
from pathlib import Path

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_file_path(user_path: str, base_dir: str) -> Path:
    """Validate file path is within base directory."""
    path = Path(user_path).resolve()
    base = Path(base_dir).resolve()
    if not str(path).startswith(str(base)):
        raise ValueError("Path traversal detected")
    return path
```

### Secure Credential Handling
```python
import os
from dotenv import load_dotenv

load_dotenv()

# Load from environment variables
API_KEY = os.getenv("API_KEY")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Never commit credentials
# Use .env file with .gitignore
```

## Conclusion

Following these best practices leads to:
- More maintainable code
- Fewer bugs
- Better performance
- Easier collaboration
- Professional code quality
