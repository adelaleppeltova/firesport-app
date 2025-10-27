import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import PrimaryButton from "../components/PrimaryButton";
import api from "../api/axios";

function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    try {
      const resp = await api.post("/auth/login", { email, password });
      const access = resp.data.access_token;
      // nastavit default header pro další volání
      api.defaults.headers.common["Authorization"] = `Bearer ${access}`;
      // zde nastavit user context / redirect
      nav("/");
    } catch (err) {
      console.error(err);
      alert("Login failed");
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
          />
        </label>

        <label className="login__label" htmlFor="password">
          Heslo:
          <input
            className="login__input"
            type="password"
            id="password"
            name="password"
            required
          />
        </label>

        <PrimaryButton
          className="btn login__button"
          onClick={() => navigate("/")}
          ariaLabel="Přihlásit se"
          type="submit"
          isLoading={false}
          //   disabled={isSubmitting}
          //   {...(isSubmitting ? "Přihlašuji..." : "Přihlásit se")}
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
