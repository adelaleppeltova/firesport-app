import { useState } from "react";
import { Link } from "react-router-dom";

import api from "../api/axios";
import PrimaryButton from "../components/PrimaryButton";

function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setMessage("");

    if (!email.includes("@") || !email.includes(".")) {
      setError("Zadejte platný email.");
      return;
    }

    setIsSubmitting(true);
    try {
      const { data } = await api.post("/v1/auth/forgot-password", { email });
      setMessage(
        data?.message ||
          "Pokud účet s tímto emailem existuje, poslali jsme instrukce pro obnovení hesla.",
      );
    } catch (err) {
      console.error("Forgot password failed:", err);
      setError("Obnovení hesla se nepodařilo odeslat. Zkuste to znovu.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="forgot-password">
      <h1 className="forgot-password__title">Obnovení hesla</h1>
      <form onSubmit={submit} className="forgot-password__form">
        <label className="forgot-password__label" htmlFor="email">
          Email:
          <input
            className="forgot-password__input"
            type="email"
            id="email"
            name="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value.toLowerCase())}
          />
        </label>
        {error && <p className="form-error">{error}</p>}
        {message && <p className="form-success">{message}</p>}
        <PrimaryButton
          className="forgot-password__button"
          aria-label="Odeslat odkaz pro obnovení hesla"
          type="submit"
          isLoading={isSubmitting}
          disabled={isSubmitting}
        >
          Odeslat odkaz
        </PrimaryButton>
      </form>
      <div className="forgot-password__content">
        <p>Vzpomněli jste si na heslo?</p>
        <Link className="forgot-password__link" to="/prihlaseni">
          Zpět na přihlášení
        </Link>
      </div>
    </div>
  );
}

export default ForgotPasswordPage;
