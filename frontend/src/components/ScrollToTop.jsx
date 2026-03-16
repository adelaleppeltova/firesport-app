import { useLayoutEffect } from "react";
import { useLocation } from "react-router-dom";

const scrollPageToTop = () => {
  window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
};

export default function ScrollToTop() {
  const { pathname } = useLocation();

  useLayoutEffect(() => {
    if ("scrollRestoration" in window.history) {
      window.history.scrollRestoration = "manual";
    }

    scrollPageToTop();
    requestAnimationFrame(scrollPageToTop);
  }, [pathname]);

  return null;
}

export { scrollPageToTop };
