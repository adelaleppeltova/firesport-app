import { Link, useNavigate } from "react-router-dom";
import PrimaryButton from "../components/PrimaryButton";

function RegisterPage() {
  const navigate = useNavigate();
  return (
    <div className="register">
      <h1 className="register__title">Registrace</h1>
      <form className="register__form">
        <label className="register__label" htmlFor="firstName">
          Jméno:
          <input
            className="register__input"
            type="text"
            id="firstName"
            name="name"
            autoComplete="given-name"
            required
          />
        </label>

        <label className="register__label" htmlFor="lastName">
          Příjmení:
          <input
            className="register__input"
            type="text"
            id="lastName"
            name="lastName"
            autoComplete="family-name"
            required
          />
        </label>

        <label className="register__label" htmlFor="email">
          Email:
          <input
            className="register__input"
            type="email"
            id="email"
            name="email"
            autoComplete="email"
            required
          />
        </label>

        <label className="register__label" htmlFor="password">
          Heslo:
          <input
            className="register__input"
            type="password"
            id="password"
            name="password"
            required
          />
        </label>

        <PrimaryButton
          className="btn register__button"
          onClick={() => navigate("/")}
          ariaLabel="Registrovat se"
          type="submit"
          isLoading={false}
          //   disabled={isSubmitting}
          //   {...(isSubmitting ? "Přihlašuji..." : "Přihlásit se")}
        >
          Registrovat se
        </PrimaryButton>
      </form>
      <div className="register__content">
        <p>Již máte účet?</p>
        <Link className="register__link" to={"/login"}>
          Přihlaste se
        </Link>
      </div>
    </div>
  );
}

export default RegisterPage;
