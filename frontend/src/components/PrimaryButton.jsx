import React from "react";

export default function PrimaryButton({
  isLoading,
  children,
  className = "",
  ...rest
}) {
  return (
    <button className={`btn ${className}`} {...rest}>
      {isLoading ? "..." : children}
    </button>
  );
}
