# Contributing Guidelines

Thank you for your interest in contributing to the Loan Officer AI Agent!

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style Guidelines](#code-style-guidelines)
- [Adding New Features](#adding-new-features)
- [Testing Requirements](#testing-requirements)
- [Documentation Standards](#documentation-standards)
- [Submitting Changes](#submitting-changes)

---

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Prioritize security and privacy

---

## Getting Started

1. **Fork the repository**

2. **Clone your fork**
```bash
git clone https://github.com/YOUR_USERNAME/loan_officer_ai.git
cd loan_officer_ai
```

3. **Set up development environment**
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt  # If exists
```

4. **Create a branch**
```bash
git checkout -b feature/your-feature-name
```

---

## Development Workflow

### Branching Strategy

- `main` - Production-ready code
- `develop` - Integration branch
- `feature/*` - New features
- `bugfix/*` - Bug fixes
- `hotfix/*` - Urgent production fixes

### Typical Workflow

```bash
# 1. Update your fork
git checkout main
git pull upstream main

# 2. Create feature branch
git checkout -b feature/add-custom-rule

# 3. Make changes and commit
git add .
git commit -m "Add custom debt ratio rule"

# 4. Push to your fork
git push origin feature/add-custom-rule

# 5. Create pull request on GitHub
```

---

## Code Style Guidelines

### Python Style (PEP 8)

```python
# ✅ Good: Clear function names, type hints, docstrings
def calculate_debt_to_income_ratio(
    monthly_income: float,
    existing_debt: float
) -> float:
    """
    Calculate the debt-to-income ratio.
    
    Args:
        monthly_income: Borrower's monthly income
        existing_debt: Total existing debt obligations
        
    Returns:
        DTI ratio as a decimal (0.0-1.0)
    """
    if monthly_income <= 0:
        return 1.0  # Maximum risk if no income
    
    return existing_debt / monthly_income


# ❌ Bad: No type hints, unclear naming, no docstring
def calc(a, b):
    if a <= 0:
        return 1.0
    return b / a
```

### Formatting

Use `black` for automatic formatting:

```bash
pip install black
black agents/ models/ utils/
```

### Linting

Use `flake8` for linting:

```bash
pip install flake8
flake8 agents/ models/ utils/ --max-line-length=100
```

### Type Checking

Use `mypy` for type checking:

```bash
pip install mypy
mypy agents/ models/
```

---

## Adding New Features

### Adding a New Agent

1. **Create agent file**
```python
# agents/credit_bureau_agent.py

class CreditBureauAgent:
    """
    Fetches and analyzes credit bureau data.
    
    Purpose: Integrate third-party credit scores
    Inputs: Borrower ID, bureau API credentials
    Outputs: Credit score, payment history
    """
    
    @staticmethod
    def fetch_credit_score(borrower_id: str) -> dict:
        """Fetch credit score from bureau API"""
        # Implementation
        pass
```

2. **Add tests**
```python
# tests/test_credit_bureau_agent.py

def test_fetch_credit_score():
    result = CreditBureauAgent.fetch_credit_score("BOR-TEST")
    assert "credit_score" in result
    assert 0 <= result["credit_score"] <= 850
```

3. **Update documentation**
- Add section to [`docs/agents.md`](./agents.md)
- Update [`docs/architecture.md`](./architecture.md) diagram

4. **Integrate with RiskAgent**
```python
# In agents/risk_agent.py

from agents.credit_bureau_agent import CreditBureauAgent

def evaluate(borrower: Borrower) -> dict:
    # Existing code...
    
    # Add credit bureau check
    if config.ENABLE_CREDIT_BUREAU:
        credit_data = CreditBureauAgent.fetch_credit_score(borrower.id)
        # Adjust risk score based on credit data
```

---

### Adding a New Endpoint

1. **Define route in main.py**
```python
@app.get("/borrower/{borrower_id}/credit-history")
async def get_credit_history(
    borrower_id: str,
    user: AuthUser = Depends(AuthAgent.get_api_key)
):
    """Get credit history for a borrower."""
    borrower = Database.get_borrower(borrower_id)
    
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")
    
    # Verify organization access
    if borrower.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    credit_data = CreditBureauAgent.fetch_credit_score(borrower_id)
    
    AuditAgent.log_event("CREDIT_CHECK", user.role, {
        "borrower_id": borrower_id,
        "org": user.organization_id
    })
    
    return credit_data
```

2. **Add to API documentation**

Update [`docs/api-reference.md`](./api-reference.md) with new endpoint details.

---

## Testing Requirements

### Required Tests

All new features must include:

1. **Unit Tests** - Test individual functions
2. **Integration Tests** - Test complete workflows
3. **Edge Case Tests** - Test boundary conditions

### Test Template

```python
import pytest
from agents.your_agent import YourAgent

class TestYourAgent:
    @pytest.fixture
    def sample_data(self):
        """Reusable test data"""
        return {...}
    
    def test_success_case(self, sample_data):
        """Test normal operation"""
        result = YourAgent.process(sample_data)
        assert result["status"] == "SUCCESS"
    
    def test_edge_case_empty_input(self):
        """Test with empty input"""
        with pytest.raises(ValueError):
            YourAgent.process({})
    
    def test_edge_case_large_values(self):
        """Test with extreme values"""
        result = YourAgent.process({"value": 999999999})
        assert result is not None
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=agents --cov=models tests/

# Run specific test file
pytest tests/test_your_agent.py -v
```

### Coverage Requirements

- **Minimum**: 70% code coverage
- **Target**: 90% code coverage for critical paths (RiskAgent, DecisionAgent)

---

## Documentation Standards

### Code Documentation

```python
def complex_function(param1: str, param2: int) -> dict:
    """
    One-line summary of what the function does.
    
    Longer description if needed, explaining:
    - Algorithm details
    - Important assumptions
    - Side effects
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Dictionary containing:
        - 'result': The main result
        - 'metadata': Additional information
        
    Raises:
        ValueError: If param2 is negative
        HTTPException: If API call fails
        
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result['result'])
        'success'
    """
    pass
```

### README Updates

When adding major features:

1. Update main [`README.md`](../README.md)
2. Add to relevant docs in [`docs/`](.)
3. Update [`CHANGELOG.md`](../CHANGELOG.md) (if exists)

---

## Submitting Changes

### Pull Request Checklist

- [ ] Code follows style guidelines (black, flake8 passing)
- [ ] All tests pass (`pytest tests/`)
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Commit messages are clear and descriptive
- [ ] No sensitive data (API keys, passwords) in code
- [ ] Type hints added for new functions
- [ ] Changelog updated (if applicable)

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Commit Message Format

```
type(scope): Brief description

Longer description if needed.

Fixes #123
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Build/config changes

**Examples:**
```
feat(risk-agent): Add credit bureau integration

Integrate with external credit bureau API to fetch
credit scores and payment history.

Closes #45
```

```
fix(auth): Resolve JWT token expiration issue

Tokens were expiring too quickly. Updated expiration
time from 15 minutes to 30 minutes.

Fixes #67
```

---

## Security Guidelines

### Never Commit

- API keys or secrets
- Service account JSON files
- Private keys or certificates
- User data or PII
- Database credentials

### Use Environment Variables

```python
# ✅ Good
import os
API_KEY = os.getenv("API_KEY")

# ❌ Bad
API_KEY = "sk_live_abc123..."
```

### Reporting Security Issues

**Do not** create public issues for security vulnerabilities.

Instead:
1. Email security contact privately
2. Describe the vulnerability
3. Wait for response before disclosing

---

## Code Review Process

### As a Contributor

- Be open to feedback
- Explain your reasoning
- Make requested changes promptly
- Keep PRs focused and small

### As a Reviewer

- Be constructive and respectful
- Explain the "why" behind suggestions
- Approve when standards are met
- Test the changes locally if needed

---

## Questions?

- Check existing documentation
- Search closed issues for similar questions
- Ask in discussions or create an issue

Thank you for contributing! 🎉
