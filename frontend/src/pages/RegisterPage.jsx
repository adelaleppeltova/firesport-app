import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import PrimaryButton from "../components/PrimaryButton";
import api from "../api/axios";
import usePersistedState, {
  clearPersistedState,
} from "../hooks/usePersistedState";

const passwordRules =
  /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d@$!%*?&#^().,_-]{8,}$/;

function RegisterPage() {
  const navigate = useNavigate();

  // persistované hodnoty
  const [firstName, setFirstName] = usePersistedState(
    "register:firstName",
    "",
    {
      ttlMs: 30 * 60_000,
    }
  );
  const [lastName, setLastName] = usePersistedState("register:lastName", "", {
    ttlMs: 30 * 60_000,
  });
  const [email, setEmail] = usePersistedState("register:email", "", {
    ttlMs: 30 * 60_000,
  });
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [showPass2, setShowPass2] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/auth/register", { email, password });
      // po úspěchu vyčistit sessionStorage
      clearPersistedState("register:firstName");
      clearPersistedState("register:lastName");
      clearPersistedState("register:email");
      navigate("/login");
    } catch (err) {
      console.error(err);
      alert("Register failed");
    }
  };

  return (
    <div className="register">
      <h1 className="register__title">Registrace</h1>
      <form onSubmit={submit} className="register__form" autoComplete="on">
        <label className="register__label" htmlFor="firstName">
          Jméno:
          <div className="text-field">
            <input
              className="register__input"
              type="text"
              id="firstName"
              name="given-name" // změněno
              autoComplete="section-register given-name" // upřesněno
              required
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
            />
          </div>
        </label>

        <label className="register__label" htmlFor="lastName">
          Příjmení:
          <div className="text-field">
            <input
              className="register__input"
              type="text"
              id="lastName"
              name="family-name" // změněno
              autoComplete="section-register family-name" // upřesněno
              required
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
            />
          </div>
        </label>

        <label className="register__label" htmlFor="email">
          Email:
          <div className="text-field">
            <input
              className="register__input"
              type="email"
              id="email"
              name="email"
              autoComplete="section-register email" // upřesněno
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
        </label>

        <label className="register__label" htmlFor="password">
          Heslo:
          <div className="password-field">
            <input
              className="register__input"
              type={showPass ? "text" : "password"}
              id="password"
              name="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPass((v) => !v)}
              aria-label={showPass ? "Skrýt heslo" : "Zobrazit heslo"}
              title={showPass ? "Skrýt heslo" : "Zobrazit heslo"}
            >
              <i
                className={
                  showPass ? "fa-solid fa-eye-slash" : "fa-solid fa-eye"
                }
              />
            </button>
          </div>
        </label>

        <label className="register__label" htmlFor="password2">
          Heslo znovu:
          <div className="password-field">
            <input
              className="register__input"
              type={showPass2 ? "text" : "password"}
              id="password2"
              name="password2"
              required
              autoComplete="new-password"
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPass2((v) => !v)}
              aria-label={showPass2 ? "Skrýt heslo" : "Zobrazit heslo"}
              title={showPass2 ? "Skrýt heslo" : "Zobrazit heslo"}
            >
              <i
                className={
                  showPass2 ? "fa-solid fa-eye-slash" : "fa-solid fa-eye"
                }
              />
            </button>
          </div>
        </label>

        <PrimaryButton
          className="btn register__button"
          ariaLabel="Registrovat se"
          type="submit"
          isLoading={false}
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
