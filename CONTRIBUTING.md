# Contributing to NPM Monitor

Thank you for your interest in contributing to NPM Monitor! This document provides guidelines for contributions.

## Development Setup

### Prerequisites
- Python 3.12+
- Docker and Docker Compose
- PostgreSQL 15+ (or use Docker)
- Git

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/your-username/npm-monitor.git
cd npm-monitor
```

2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -e ".[dev]"
```

4. **Setup pre-commit hooks**
```bash
pre-commit install
```

5. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

6. **Start services**
```bash
docker compose up -d postgres
```

## Code Style

### Python
- Follow PEP 8 guidelines
- Use type hints for all functions
- Maximum line length: 120 characters
- Use `ruff` for formatting and linting

### Code Organization
```
src/
├── app.py              # Main Streamlit application
├── auth.py             # Authentication logic
├── config.py           # Configuration management
├── database.py         # Database operations
├── log_parser.py       # Log parsing utilities
├── sync.py             # Log synchronization
├── utils.py            # Helper functions
└── components/         # Streamlit UI components
    ├── charts.py
    ├── tables.py
    └── sidebar.py
```

### Naming Conventions
- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`

## Testing

### Run Tests
```bash
# Run all tests
python3 -m pytest tests/ -v

# Run with coverage
python3 -m pytest tests/ --cov=src --cov-report=html

# Run specific test
python3 -m pytest tests/test_database.py -v
```

### Writing Tests
- Place tests in `tests/` directory
- Use `pytest` framework
- Mock external dependencies
- Aim for >80% code coverage

#### Example Test
```python
import pytest
from unittest.mock import Mock, patch

def test_function():
    """Test description."""
    # Arrange
    input_data = "test"
    
    # Act
    result = function_under_test(input_data)
    
    # Assert
    assert result == expected_output
```

## Commit Messages

### Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

### Examples
```
feat(auth): add IP-based access control

- Add network whitelist configuration
- Implement IP validation in authentication
- Add tests for IP filtering

Closes #123
```

```
fix(database): resolve connection pool leak

Connection pool was not properly closing connections,
leading to resource exhaustion under load.

Fixes #456
```

## Pull Request Process

1. **Create feature branch**
```bash
git checkout -b feature/your-feature-name
```

2. **Make changes and commit**
```bash
git add .
git commit -m "feat: your feature"
```

3. **Run tests and linting**
```bash
python3 -m pytest tests/ -v
ruff check src/
ruff format src/
```

4. **Push to repository**
```bash
git push origin feature/your-feature-name
```

5. **Open Pull Request**
- Describe changes in PR description
- Link related issues
- Request review from maintainers

### PR Checklist
- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] No merge conflicts

## Database Migrations

### Adding Columns
```python
# In database.py init_database()
new_columns = [
    ("new_column", "TEXT"),
]

for col_name, col_type in new_columns:
    cur.execute(f"""
        DO $$
        BEGIN
            ALTER TABLE traffic ADD COLUMN {col_name} {col_type};
        EXCEPTION
            WHEN duplicate_column THEN NULL;
        END $$;
    """)
```

### Creating Indexes
```python
indexes = [
    ("idx_name", "table (column1, column2)"),
]

for idx_name, idx_def in indexes:
    cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def};")
```

## Performance Guidelines

### Database Queries
- Use indexes for filtered columns
- Batch inserts for bulk operations
- Use connection pooling
- Set query timeouts

### Caching
- Use `@st.cache_data` for dashboard data
- Implement TTL for time-sensitive data
- Clear cache on data updates

### Logging
- Use structured logging
- Avoid logging sensitive data
- Use appropriate log levels

## Security Guidelines

### Authentication
- Never hardcode credentials
- Use environment variables
- Validate all inputs
- Use parameterized queries

### Data Protection
- Don't log sensitive information
- Sanitize user inputs
- Use read-only permissions where possible
- Implement rate limiting

## Documentation

### Code Comments
```python
def complex_function(param1: str, param2: int) -> dict:
    """
    Brief description of function.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When invalid input provided
    """
    # Implementation
```

### README Updates
- Update feature list
- Update configuration table
- Update example commands

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create git tag
4. Build and push Docker image
5. Create GitHub release

## Getting Help

- Open an issue for bugs
- Use discussions for questions
- Join our chat for general discussion

## License

By contributing, you agree that your contributions will be licensed under the MIT License.