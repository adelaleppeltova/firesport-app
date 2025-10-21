import { Link, useNavigate } from "react-router-dom";
import PrimaryButton from "../components/PrimaryButton";
// import { useForm } from "react-hook-form";
// import { zodResolver } from "@hookform/resolvers/zod";

// const schema = z.object({
//   email: z.string().email("Neplatný e-mail"),
//   password: z.string().min(6, "Min. 6 znaků"),
// });

function LoginPage() {
  const navigate = useNavigate();

  //   const {
  //     register,
  //     handleSubmit,
  //     formState: { errors, isSubmitting },
  //   } = useForm({ resolver: zodResolver(schema) });
  return (
    <div className="login">
      <h1 className="login__title">Přihlášení</h1>
      <form className="login__form">
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
