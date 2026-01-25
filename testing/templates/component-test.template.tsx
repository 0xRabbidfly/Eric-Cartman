import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FluentProvider, webLightTheme } from '@fluentui/react-components';
import { ComponentName } from '@/components/path/ComponentName';

/**
 * React Component Test Template
 *
 * Use this template for testing React components with Fluent UI.
 * Adjust imports and mocks based on component dependencies.
 */

// Mock next-intl
vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => 'en',
}));

// Helper to render with Fluent UI provider
const renderWithProviders = (ui: React.ReactElement) => {
  return render(
    <FluentProvider theme={webLightTheme}>
      {ui}
    </FluentProvider>
  );
};

describe('ComponentName', () => {
  it('renders with required props', () => {
    renderWithProviders(<ComponentName title="Test Title" />);

    expect(screen.getByText('Test Title')).toBeInTheDocument();
  });

  it('handles user interaction', () => {
    const onClickMock = vi.fn();
    renderWithProviders(<ComponentName onClick={onClickMock} />);

    const button = screen.getByRole('button');
    fireEvent.click(button);

    expect(onClickMock).toHaveBeenCalledOnce();
  });

  it('applies correct accessibility attributes', () => {
    renderWithProviders(<ComponentName title="Test" />);

    const element = screen.getByRole('heading');
    expect(element).toHaveAttribute('aria-label', 'Test');
  });

  it('renders different variants correctly', () => {
    const { rerender } = renderWithProviders(
      <ComponentName variant="primary" />
    );

    expect(screen.getByTestId('component')).toHaveClass('variant-primary');

    rerender(
      <FluentProvider theme={webLightTheme}>
        <ComponentName variant="secondary" />
      </FluentProvider>
    );

    expect(screen.getByTestId('component')).toHaveClass('variant-secondary');
  });
});
