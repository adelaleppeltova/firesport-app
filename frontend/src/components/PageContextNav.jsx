import { Link } from "react-router-dom";

export default function PageContextNav({ items = [], action }) {
  const visibleItems = items.filter(Boolean);

  if (visibleItems.length === 0 && !action) {
    return null;
  }

  return (
    <div className="page-context-nav" aria-label="Navigace stránky">
      {visibleItems.length > 0 && (
        <nav className="page-context-nav__breadcrumbs" aria-label="Breadcrumb">
          {visibleItems.map((item, index) => {
            const isLast = index === visibleItems.length - 1;

            return (
              <span className="page-context-nav__crumb" key={`${item.label}-${index}`}>
                {item.to && !isLast ? (
                  <Link className="page-context-nav__link" to={item.to}>
                    {item.label}
                  </Link>
                ) : (
                  <span className="page-context-nav__current">{item.label}</span>
                )}
                {!isLast && (
                  <span className="page-context-nav__separator" aria-hidden="true">
                    /
                  </span>
                )}
              </span>
            );
          })}
        </nav>
      )}

      {action?.to && action?.label && (
        <Link className="page-context-nav__action" to={action.to}>
          {action.label}
        </Link>
      )}
    </div>
  );
}
