import { Link, useNavigate, Navigate } from "react-router-dom";
import PrimaryButton from "../components/PrimaryButton";
import { useAuth } from "../context/AuthContext";

function WelcomePage() {
  const navigate = useNavigate();
  const { isAuthenticated, loading } = useAuth();

  if (loading) return <div>Loading...</div>;
  if (isAuthenticated) return <Navigate to="/domu" replace />;

  return (
    <div className="welcome">
      <main className="welcome__main">
        <h1 className="welcome__title">Vítejte</h1>
        <PrimaryButton
          className="btn welcome__button"
          onClick={() => navigate("/prihlaseni")}
          aria-label="Přihlásit se"
          type="button"
          isLoading={false}
          disabled={false}
        >
          Přihlásit se
        </PrimaryButton>
        <div className="welcome__content">
          <p>Nemáte účet?</p>
          <Link className="welcome__link" to={"/registrace"}>
            Zaregistrujte se
          </Link>
        </div>
      </main>
    </div>
  );
}

export default WelcomePage;
