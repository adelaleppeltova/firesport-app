const Card = ({ title, children, status = "ready", className = "" }) => {
  return (
    <div className={`card ${className} ${status ? `card--${status}` : ""}`}>
      {title && <h2 className="card__title">{title}</h2>}
      {children ? <div className="card__content">{children}</div> : null}
    </div>
  );
};

export default Card;
