import { Link } from "react-router-dom";

const ErrorPage = ({
  statusCode = 404,
  title,
  description,
  backTo = "/domu",
}) => {
  const resolvedTitle =
    title ?? (statusCode === 403 ? "Přístup odepřen" : "Stránka nenalezena");
  const resolvedDescription =
    description ??
    (statusCode === 403
      ? "Na tuto stránku nemáš oprávnění."
      : "Omlouváme se, ale stránka kterou hledáš neexistuje.");

  return (
    <div className="error-page page">
      <h1>
        {statusCode} - {resolvedTitle}
      </h1>
      <p>{resolvedDescription}</p>
      <Link to={backTo} className="btn btn-primary">
        Zpět na domovskou stránku
      </Link>
    </div>
  );
};

export default ErrorPage;
