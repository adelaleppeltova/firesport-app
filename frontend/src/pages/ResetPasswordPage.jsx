import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import api from "../api/axios";
import PrimaryButton from "../components/PrimaryButton";
import { hashPassword } from "../utils/passwordHash";

const passwordRules =
  /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d@$!%*?&#^().,_-]{8,}$/;

function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [showPass2, setShowPass2] = useState(false);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");

    if (!token) {
      setError("Resetovací odkaz je neplatný nebo neúplný.");
      return;
    }

    if (password !== password2) {
      setError("Hesla se neshodují.");
      return;
    }

    if (!passwordRules.test(password)) {
      setError(
        "Heslo musí obsahovat min. 8 znaků, velké a malé písmeno a číslici.",
      );
      return;
    }

    setIsSubmitting(true);
    try {
      const passwordHash = await hashPassword(password);
      await api.post("/v1/auth/reset-password", {
        token,
        password_hash: passwordHash,
      });
      navigate("/prihlaseni", {
        state: {
          flash: {
            type: "success",
            message: "Heslo bylo změněno. Přihlaste se novým heslem.",
          },
        },
      });
    } catch (err) {
      console.error("Reset password failed:", err);
      setError("Reset hesla selhal. Odkaz mohl vypršet.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="reset-password">
      <h1 className="reset-password__title">Nové heslo</h1>
      <form onSubmit={submit} className="reset-password__form">
        <label className="reset-password__label" htmlFor="password">
          Nové heslo:
          <div className="password-field">
            <input
              className="reset-password__input"
              type={showPass ? "text" : "password"}
              id="password"
              name="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
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
        <label className="reset-password__label" htmlFor="password2">
          Nové heslo znovu:
          <div className="password-field">
            <input
              className="reset-password__input"
              type={showPass2 ? "text" : "password"}
              id="password2"
              name="password2"
              autoComplete="new-password"
              required
              value={password2}
              onChange={(e) => setPassword2(e.target.value)}
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
        {error && <p className="form-error">{error}</p>}
        <PrimaryButton
          className="reset-password__button"
          aria-label="Uložit nové heslo"
          type="submit"
          isLoading={isSubmitting}
          disabled={isSubmitting}
        >
          Uložit heslo
        </PrimaryButton>
      </form>
      <div className="reset-password__content">
        <p>Potřebujete nový odkaz?</p>
        <Link className="reset-password__link" to="/zapomenute-heslo">
          Požádat znovu
        </Link>
      </div>
    </div>
  );
}

export default ResetPasswordPage;
