import { Link, useNavigate } from "react-router-dom";
import PrimaryButton from "../components/PrimaryButton";

function WelcomePage() {
  const navigate = useNavigate();
  return (
    <div className="welcome">
      <main className="welcome__main">
        <h1 className="welcome__title">Vítejte</h1>
        <PrimaryButton
          className="btn welcome__button"
          onClick={() => navigate("/login")}
          ariaLabel="Přihlásit se"
          type="button"
          isLoading={false}
          disabled={false}
        >
          Přihlásit se
        </PrimaryButton>
        <div className="welcome__content">
          <p>Nemáte účet?</p>
          <Link className="welcome__link" to={"/register"}>
            Zaregistrujte se
          </Link>
        </div>
      </main>
    </div>
  );
}

export default WelcomePage;
