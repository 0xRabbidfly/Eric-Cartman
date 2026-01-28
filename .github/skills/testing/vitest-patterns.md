# Vitest Unit Test Patterns

Complete patterns for testing different types of components and code in the AI-HUB-Portal.

## Server Component Test

Next.js Server Components (RSC) - default in App Router.

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ComponentName } from '@/components/content/ComponentName';

// Mock next-intl for i18n
vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => 'en',
}));

describe('ComponentName', () => {
  it('renders with required props', () => {
    render(<ComponentName title="Test Title" />);
    expect(screen.getByText('Test Title')).toBeInTheDocument();
  });

  it('applies correct ARIA attributes', () => {
    render(<ComponentName title="Test" />);
    const element = screen.getByRole('heading');
    expect(element).toHaveAttribute('aria-label', 'Test');
  });
});
```

## Client Component Test

Components with `"use client"` directive (interactive components).

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FluentProvider, webLightTheme } from '@fluentui/react-components';
import { InteractiveComponent } from '@/components/ui/InteractiveComponent';

// Wrap Fluent UI components with provider
const renderWithFluent = (ui: React.ReactNode) => {
  return render(
    <FluentProvider theme={webLightTheme}>
      {ui}
    </FluentProvider>
  );
};

describe('InteractiveComponent', () => {
  it('handles click events', async () => {
    const onClick = vi.fn();
    renderWithFluent(<InteractiveComponent onClick={onClick} />);

    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('updates state on user input', () => {
    renderWithFluent(<InteractiveComponent />);

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'test input' } });

    expect(input).toHaveValue('test input');
  });
});
```

## API Route Handler Test

Testing Next.js App Router API routes.

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { GET, POST } from '@/app/api/search/route';
import { NextRequest } from 'next/server';
import { getServerSession } from 'next-auth';

// Mock authentication
vi.mock('next-auth', () => ({
  getServerSession: vi.fn()
}));

describe('API Route: /api/search', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns 401 when not authenticated', async () => {
    vi.mocked(getServerSession).mockResolvedValue(null);

    const request = new NextRequest('http://localhost:3000/api/search?q=test');
    const response = await GET(request);

    expect(response.status).toBe(401);
  });

  it('returns search results for authenticated user', async () => {
    vi.mocked(getServerSession).mockResolvedValue({
      user: { email: 'test@example.com', name: 'Test User' }
    });

    const request = new NextRequest('http://localhost:3000/api/search?q=AI');
    const response = await GET(request);

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('results');
  });
});
```

## Hook Test

Testing custom React hooks.

```typescript
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useLocalStorage } from '@/lib/hooks/useLocalStorage';

describe('useLocalStorage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('initializes with default value', () => {
    const { result } = renderHook(() => useLocalStorage('key', 'default'));
    expect(result.current[0]).toBe('default');
  });

  it('updates localStorage when value changes', () => {
    const { result } = renderHook(() => useLocalStorage('key', 'initial'));

    act(() => {
      result.current[1]('updated');
    });

    expect(result.current[0]).toBe('updated');
    expect(localStorage.getItem('key')).toBe(JSON.stringify('updated'));
  });

  it('retrieves existing value from localStorage', () => {
    localStorage.setItem('key', JSON.stringify('existing'));

    const { result } = renderHook(() => useLocalStorage('key', 'default'));
    expect(result.current[0]).toBe('existing');
  });
});
```

## Utility Function Test

Testing pure utility functions.

```typescript
import { describe, it, expect } from 'vitest';
import { formatDate, calculatePagination } from '@/lib/utils';

describe('formatDate', () => {
  it('formats date in EN locale', () => {
    const date = new Date('2026-01-24');
    expect(formatDate(date, 'en')).toBe('January 24, 2026');
  });

  it('formats date in FR locale', () => {
    const date = new Date('2026-01-24');
    expect(formatDate(date, 'fr')).toBe('24 janvier 2026');
  });
});

describe('calculatePagination', () => {
  it('returns correct pagination for first page', () => {
    const result = calculatePagination(1, 10, 100);
    expect(result).toEqual({
      currentPage: 1,
      totalPages: 10,
      startIndex: 0,
      endIndex: 10,
    });
  });
});
```

## Async Component Test

Testing components with async data fetching.

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AsyncComponent } from '@/components/content/AsyncComponent';

// Mock fetch
global.fetch = vi.fn();

describe('AsyncComponent', () => {
  it('displays loading state', () => {
    vi.mocked(fetch).mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<AsyncComponent />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('displays data when loaded', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ title: 'Test Data' })
    } as Response);

    render(<AsyncComponent />);

    await waitFor(() => {
      expect(screen.getByText('Test Data')).toBeInTheDocument();
    });
  });

  it('displays error on fetch failure', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Network error'));

    render(<AsyncComponent />);

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });
});
```

## Snapshot Testing

For visual regression testing.

```typescript
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { StaticComponent } from '@/components/content/StaticComponent';

describe('StaticComponent', () => {
  it('matches snapshot', () => {
    const { container } = render(<StaticComponent title="Test" />);
    expect(container.firstChild).toMatchSnapshot();
  });

  it('matches snapshot with different props', () => {
    const { container } = render(
      <StaticComponent title="Different" variant="secondary" />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
```

## Form Validation Test

Testing forms with validation.

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import userEvent from '@testing-library/user-event';
import { SearchForm } from '@/components/search/SearchForm';

describe('SearchForm', () => {
  it('shows validation error for empty input', async () => {
    const onSubmit = vi.fn();
    render(<SearchForm onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByText(/required/i)).toBeInTheDocument();
    });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits form with valid input', async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    render(<SearchForm onSubmit={onSubmit} />);

    await user.type(screen.getByRole('textbox'), 'test query');
    await user.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ query: 'test query' });
    });
  });
});
```

## Common Testing Utilities

### Test Helpers

```typescript
// test-utils.tsx
import { FluentProvider, webLightTheme } from '@fluentui/react-components';
import { ReactNode } from 'react';

export function renderWithProviders(ui: ReactNode) {
  return render(
    <FluentProvider theme={webLightTheme}>
      {ui}
    </FluentProvider>
  );
}

export function mockNextIntl() {
  vi.mock('next-intl', () => ({
    useTranslations: () => (key: string) => key,
    useLocale: () => 'en',
  }));
}
```

### Mock Data

```typescript
// test-fixtures.ts
export const mockUser = {
  id: 'test-user-id',
  email: 'test@example.com',
  name: 'Test User',
};

export const mockSearchResults = {
  results: [
    { id: '1', title: 'Result 1', url: 'https://example.com/1' },
    { id: '2', title: 'Result 2', url: 'https://example.com/2' },
  ],
  total: 2,
};
```
