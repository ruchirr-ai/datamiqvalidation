---
inclusion: always
---

# Testing Standards

## Testing Philosophy

**CRITICAL**: Create test cases for everything. Every feature added must have corresponding test cases with sample payloads.

## Test-Driven Development

### Test Creation Requirements
- Write tests BEFORE or ALONGSIDE feature implementation
- Every new feature MUST have test cases
- Every API endpoint MUST have test cases with sample payloads
- Every UI component MUST have test cases
- Every service/utility function MUST have test cases

### Test Coverage Goals
- Minimum 80% code coverage for backend
- Minimum 70% code coverage for frontend
- 100% coverage for critical paths (authentication, authorization, data encryption)

## Backend Testing

### Unit Tests

#### What to Test
- Individual functions and methods
- Service layer logic
- Repository operations
- Utility functions
- Data transformations
- Validation logic

#### Test Structure
```python
def test_feature_name_scenario():
    """Test description explaining what is being tested"""
    # Arrange - Set up test data
    sample_payload = {
        "username": "testuser",
        "password": "TestPass123"
    }
    
    # Act - Execute the function
    result = function_under_test(sample_payload)
    
    # Assert - Verify the result
    assert result.status == "success"
    assert result.data["username"] == "testuser"
```

#### Sample Payloads
Always include sample payloads in tests:
```python
# Valid payload
valid_login_payload = {
    "username": "admin",
    "password": "SecurePass123!"
}

# Invalid payload - missing field
invalid_payload_missing_field = {
    "username": "admin"
    # password missing
}

# Invalid payload - wrong type
invalid_payload_wrong_type = {
    "username": 123,
    "password": "SecurePass123!"
}

# Edge case - empty strings
edge_case_empty = {
    "username": "",
    "password": ""
}

# Edge case - very long strings
edge_case_long = {
    "username": "a" * 1000,
    "password": "b" * 1000
}
```

### Integration Tests

#### What to Test
- API endpoint flows
- Database interactions
- Redis caching behavior
- AWS service integrations
- Multi-component interactions

#### API Endpoint Tests
Every API endpoint MUST have tests for:
1. **Success case** with valid payload
2. **Validation errors** with invalid payloads
3. **Authentication errors** with missing/invalid tokens
4. **Authorization errors** with insufficient permissions
5. **Edge cases** (empty data, large data, special characters)

#### Example API Test
```python
def test_login_endpoint_success():
    """Test POST /api/auth/login with valid credentials"""
    # Sample payload
    payload = {
        "username": "admin",
        "password": "AdminPass123!"
    }
    
    response = client.post("/api/auth/login", json=payload)
    
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["user"]["username"] == "admin"

def test_login_endpoint_invalid_credentials():
    """Test POST /api/auth/login with invalid credentials"""
    # Sample payload with wrong password
    payload = {
        "username": "admin",
        "password": "WrongPassword"
    }
    
    response = client.post("/api/auth/login", json=payload)
    
    assert response.status_code == 401
    assert "error" in response.json()

def test_login_endpoint_missing_field():
    """Test POST /api/auth/login with missing field"""
    # Sample payload missing password
    payload = {
        "username": "admin"
    }
    
    response = client.post("/api/auth/login", json=payload)
    
    assert response.status_code == 400
    assert "password" in response.json()["error"].lower()
```

### Property-Based Tests

#### What to Test
- Universal properties that should hold for all inputs
- Data transformations (encryption/decryption, hashing)
- Idempotent operations
- Invariants (e.g., "hashed password should never equal plain password")

#### Configuration
- Minimum 100 iterations per property test
- Use Hypothesis library for Python

#### Example Property Test
```python
from hypothesis import given, strategies as st

@given(password=st.text(min_size=8, max_size=128))
def test_password_hashing_round_trip(password):
    """Property: Any password should hash and verify correctly"""
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert not verify_password(password + "wrong", hashed)
```

### Database Tests

#### What to Test
- CRUD operations
- Transactions and rollbacks
- Constraints and validations
- Indexes and query performance
- Data integrity

#### Sample Test
```python
def test_create_user_in_database():
    """Test user creation with sample data"""
    # Sample user data
    user_data = {
        "username": "testuser",
        "password_hash": "hashed_password_here",
        "role": "user"
    }
    
    user = user_repository.create_user(**user_data)
    
    assert user.id is not None
    assert user.username == "testuser"
    assert user.role == "user"
    
    # Cleanup
    user_repository.delete_user(user.id)
```

## Frontend Testing

### Component Tests

#### What to Test
- Component rendering
- User interactions (clicks, typing, form submission)
- Props handling
- State changes
- Conditional rendering
- Error states

#### Test Structure
```typescript
describe('LoginForm', () => {
  it('renders with all required fields', () => {
    render(<LoginForm />);
    
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
  });
  
  it('submits form with valid credentials', async () => {
    const mockOnSubmit = jest.fn();
    render(<LoginForm onSubmit={mockOnSubmit} />);
    
    // Sample input data
    await userEvent.type(screen.getByLabelText(/username/i), 'testuser');
    await userEvent.type(screen.getByLabelText(/password/i), 'TestPass123!');
    await userEvent.click(screen.getByRole('button', { name: /login/i }));
    
    expect(mockOnSubmit).toHaveBeenCalledWith({
      username: 'testuser',
      password: 'TestPass123!'
    });
  });
  
  it('displays error message on login failure', async () => {
    const mockOnSubmit = jest.fn().mockRejectedValue(new Error('Invalid credentials'));
    render(<LoginForm onSubmit={mockOnSubmit} />);
    
    await userEvent.type(screen.getByLabelText(/username/i), 'testuser');
    await userEvent.type(screen.getByLabelText(/password/i), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: /login/i }));
    
    expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument();
  });
});
```

### API Integration Tests

#### What to Test
- API calls with sample payloads
- Response handling
- Error handling
- Loading states
- Token management

#### Example Test
```typescript
describe('authApi', () => {
  it('calls login endpoint with correct payload', async () => {
    const mockResponse = {
      access_token: 'token123',
      user: { id: 1, username: 'testuser', role: 'user' }
    };
    
    // Mock API call
    jest.spyOn(axios, 'post').mockResolvedValue({ data: mockResponse });
    
    // Sample payload
    const credentials = {
      username: 'testuser',
      password: 'TestPass123!'
    };
    
    const result = await authApi.login(credentials);
    
    expect(axios.post).toHaveBeenCalledWith('/api/auth/login', credentials);
    expect(result.access_token).toBe('token123');
  });
});
```

### End-to-End Tests

#### What to Test
- Complete user flows
- Multi-page interactions
- Authentication flows
- Critical business processes

#### Example E2E Test
```typescript
describe('Login Flow', () => {
  it('allows user to login and navigate to dashboard', async () => {
    // Navigate to login page
    await page.goto('http://localhost:3000/login');
    
    // Fill in credentials (sample data)
    await page.fill('[name="username"]', 'admin');
    await page.fill('[name="password"]', 'AdminPass123!');
    
    // Submit form
    await page.click('button[type="submit"]');
    
    // Verify redirect to dashboard
    await page.waitForURL('**/dashboard');
    expect(page.url()).toContain('/dashboard');
    
    // Verify user is logged in
    expect(await page.textContent('.user-profile')).toContain('admin');
  });
});
```

## Test Data Management

### Sample Payloads Repository

Create a centralized location for sample payloads:

```python
# tests/fixtures/sample_payloads.py

# Authentication payloads
VALID_LOGIN = {
    "username": "admin",
    "password": "AdminPass123!"
}

INVALID_LOGIN_WRONG_PASSWORD = {
    "username": "admin",
    "password": "WrongPassword"
}

INVALID_LOGIN_MISSING_FIELD = {
    "username": "admin"
}

# User creation payloads
VALID_USER_CREATE = {
    "username": "newuser",
    "password": "NewPass123!",
    "role": "user"
}

# Database connection payloads
VALID_DB_CONNECTION = {
    "name": "Production DB",
    "type": "postgresql",
    "host": "db.example.com",
    "port": 5432,
    "database": "mydb",
    "username": "dbuser",
    "password": "DbPass123!"
}

# Migration project payloads
VALID_MIGRATION_PROJECT = {
    "name": "Customer Data Migration",
    "source_connection_id": 1,
    "target_connection_id": 2,
    "description": "Migrate customer data from MySQL to PostgreSQL"
}
```

### Test Fixtures

Use fixtures for common test setup:

```python
import pytest

@pytest.fixture
def sample_user():
    """Fixture providing a sample user"""
    return {
        "id": 1,
        "username": "testuser",
        "role": "user",
        "created_at": "2026-01-25T10:00:00Z"
    }

@pytest.fixture
def authenticated_client(client, sample_user):
    """Fixture providing an authenticated API client"""
    token = generate_test_token(sample_user)
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

## Test Organization

### Directory Structure

```
backend/
  tests/
    unit/
      test_auth_service.py
      test_user_repository.py
      test_rbac_service.py
    integration/
      test_auth_endpoints.py
      test_database_operations.py
    property/
      test_password_hashing.py
      test_token_generation.py
    fixtures/
      sample_payloads.py
      test_fixtures.py
    conftest.py

frontend/
  src/
    components/
      ui/
        Button.test.tsx
        Input.test.tsx
    pages/
      LoginScreen.test.tsx
    services/
      authApi.test.ts
    __tests__/
      e2e/
        login-flow.test.ts
```

## Test Naming Conventions

### Backend Tests
- `test_<function_name>_<scenario>()` for unit tests
- `test_<endpoint>_<http_method>_<scenario>()` for API tests
- `test_<property_name>()` for property tests

### Frontend Tests
- `<ComponentName>.test.tsx` for component tests
- `<serviceName>.test.ts` for service tests
- `<feature>-flow.test.ts` for E2E tests

## Continuous Testing

### Pre-Commit Checks
- Run unit tests before committing
- Run linters and formatters
- Check test coverage

### CI/CD Pipeline
- Run all tests on every pull request
- Run integration tests on merge to main
- Run E2E tests before deployment
- Generate and publish coverage reports

### Test Execution
```bash
# Backend
pytest tests/unit -v
pytest tests/integration -v
pytest tests/property -v --hypothesis-profile=ci

# Frontend
npm test
npm run test:coverage
npm run test:e2e
```

## Test Documentation

### Test Comments
Every test should have a docstring explaining:
- What is being tested
- What the expected behavior is
- Any special setup or conditions

### Sample Payload Documentation
Document all sample payloads with:
- Purpose of the payload
- Expected result when used
- Any special characteristics

## Best Practices

### DO
- Write tests for every new feature
- Include sample payloads in all tests
- Test both success and failure cases
- Test edge cases and boundary conditions
- Use descriptive test names
- Keep tests independent and isolated
- Mock external dependencies
- Clean up test data after tests

### DON'T
- Skip writing tests to save time
- Write tests that depend on other tests
- Use production data in tests
- Hardcode sensitive data in tests
- Write tests that are flaky or non-deterministic
- Test implementation details instead of behavior
- Leave commented-out test code

## Test Maintenance

### Regular Reviews
- Review and update tests when requirements change
- Remove obsolete tests
- Refactor tests to improve readability
- Update sample payloads to reflect current data models

### Test Debt
- Track and prioritize missing tests
- Add tests for bugs discovered in production
- Improve coverage for critical paths
- Refactor brittle or flaky tests
