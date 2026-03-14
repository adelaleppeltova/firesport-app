import { useState } from "react";
import { useNavigate } from "react-router-dom";
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
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");

    // validace emailu
    if (!email.includes("@") || !email.includes(".")) {
      setError("Zadejte platný email.");
      return;
    }

    // validace min. délky hesla
    if (password.length < 8) {
      setError("Heslo musí mít alespoň 8 znaků.");
      return;
    }

    setIsSubmitting(true);
    try {
      await login(email, password);
      clearPersistedState("login:email");
      navigate("/", {
        state: {
          flash: { type: "success", message: "Přihlášení proběhlo úspěšně." },
        },
      });
    } catch (err) {
      console.error("Login failed:", err);
      setError("Nesprávný email nebo heslo.");
    } finally {
      setIsSubmitting(false);
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
            onChange={(e) => setEmail(e.target.value.toLowerCase())}
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
        {error && <p className="form-error">{error}</p>} {/* přidáno */}
        <PrimaryButton
          className="btn login__button"
          aria-label="Přihlásit se"
          type="submit"
          isLoading={isSubmitting}
          disabled={isSubmitting}
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
