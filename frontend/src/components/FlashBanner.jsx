import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

export default function FlashBanner() {
  const location = useLocation();
  const flash = location.state?.flash;
  const [visible, setVisible] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);

  useEffect(() => {
    if (!flash) {
      setVisible(false);
      setFadeOut(false);
      return;
    }
    setVisible(true);
    setFadeOut(false);

    const fadeTimer = setTimeout(() => setFadeOut(true), 3700);
    const hideTimer = setTimeout(() => setVisible(false), 4000);

    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(hideTimer);
    };
  }, [flash]);

  if (!flash || !visible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`flash-banner flash-banner--${flash.type} ${
        fadeOut ? "flash-banner--fade-out" : "flash-banner--fade-in"
      }`}
    >
      <span>{flash.message}</span>
      <button
        type="button"
        className="flash-banner__close"
        onClick={() => {
          setFadeOut(true);
          setTimeout(() => setVisible(false), 300);
        }}
        aria-label="Zavřít"
      >
        ×
      </button>
    </div>
  );
}
