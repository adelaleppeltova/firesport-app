import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { setAuthToken } from "../api/axios";
import PrimaryButton from "../components/PrimaryButton";
import { useAuth } from "../context/AuthContext";
import { Link } from "react-router-dom";
import usePersistedState, {
  clearPersistedState,
} from "../hooks/usePersistedState";

function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = usePersistedState("login:email", "", {
    ttlMs: 30 * 60_000,
  });
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await login(email, password);
      clearPersistedState("login:email"); // po úspěchu smazat
      navigate("/");
    } catch (err) {
      console.error("Login failed:", err);
      alert(err?.response?.data?.detail || "Login failed");
    }
  };

  return (
    <div className="login">
      <h1 className="login__title">Přihlášení</h1>
      <form onSubmit={submit} className="login__form">
        <label className="login__label" htmlFor="email">
          Email:
          <input
            className="login__input"
            type="email"
            id="email"
            name="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        <label className="login__label" htmlFor="password">
          Heslo:
          <div className="password-field">
            <input
              className="login__input"
              type={showPassword ? "text" : "password"}
              id="password"
              name="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Skrýt heslo" : "Zobrazit heslo"}
              title={showPassword ? "Skrýt heslo" : "Zobrazit heslo"}
            >
              <i
                className={
                  showPassword ? "fa-solid fa-eye-slash" : "fa-solid fa-eye"
                }
              />
            </button>
          </div>
        </label>

        <PrimaryButton
          className="btn login__button"
          aria-label="Přihlásit se"
          type="submit"
          isLoading={false}
        >
          Přihlásit se
        </PrimaryButton>
      </form>
      <div className="login__content">
        <p>Nemáte účet?</p>
        <Link className="login__link" to={"/register"}>
          Zaregistrujte se
        </Link>
      </div>
    </div>
  );
}

export default LoginPage;
