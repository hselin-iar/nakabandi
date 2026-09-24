/**
 * Select.tsx — Themed dropdown built on @radix-ui/react-select.
 *
 * Replaces native <select> everywhere in the app: a native select can only be styled on its
 * closed box — the open option list renders with whatever the OS/browser gives it, which is
 * the "looks unfinished" part users notice. Radix owns keyboard/focus/positioning; every pixel
 * of both the closed trigger and the open list is themed here with the existing `.nk-btn`-style
 * tokens.
 */

import * as SelectPrimitive from "@radix-ui/react-select";

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  id?: string;
  ariaLabel?: string;
  size?: "sm" | "md";
  disabled?: boolean;
  placeholder?: string;
  /** data-testid on the trigger button, for tests that locate the control directly. */
  testId?: string;
}

export function Select({
  value,
  onValueChange,
  options,
  id,
  ariaLabel,
  size = "md",
  disabled,
  placeholder,
  testId,
}: SelectProps) {
  return (
    <SelectPrimitive.Root value={value} onValueChange={onValueChange} disabled={disabled}>
      <SelectPrimitive.Trigger
        id={id}
        aria-label={ariaLabel}
        data-testid={testId}
        className={`nk-select-trigger nk-select-trigger--${size}`}
      >
        <SelectPrimitive.Value placeholder={placeholder} />
        <SelectPrimitive.Icon className="nk-select-trigger__icon" aria-hidden="true">
          ▾
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          className="nk-select-content"
          position="popper"
          sideOffset={4}
        >
          <SelectPrimitive.Viewport className="nk-select-viewport">
            {options.map((opt) => (
              <SelectPrimitive.Item key={opt.value} value={opt.value} className="nk-select-item">
                <SelectPrimitive.ItemText>{opt.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator className="nk-select-item__indicator">
                  ✓
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
