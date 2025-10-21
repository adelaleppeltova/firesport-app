import React from "react";

function PrimaryButton({
  className,
  onClick,
  ariaLabel,
  children,
  type,
  isLoading,
  disabled,
}) {
  return (
    <button
      className={className}
      onClick={onClick}
      type={type}
      isLoading={isLoading}
      aria-label={ariaLabel}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

export default PrimaryButton;
