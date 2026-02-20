import { Link } from "react-router-dom";

const ErrorPage = () => {
  return (
    <div className="error-page page">
      <h1>404 - Stránka nenalezena</h1>
      <p>Omlouváme se, ale stránka kterou hledáš neexistuje.</p>
      <Link to="/home" className="btn btn-primary">
        Zpět na domovskou stránku
      </Link>
    </div>
  );
};

export default ErrorPage;
