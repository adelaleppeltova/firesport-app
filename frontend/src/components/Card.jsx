const Card = ({
  title,
  content,
  children,
  status = "ready",
  className = "",
}) => {
  return (
    <div className={`card ${className} ${status ? `card--${status}` : ""}`}>
      {title && <h2 className="card-title">{title}</h2>}
      {children ? (
        <div className="card-content">{children}</div>
      ) : content ? (
        <p className="card-content">{content}</p>
      ) : null}
    </div>
  );
};

export default Card;
