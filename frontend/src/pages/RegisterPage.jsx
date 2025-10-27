import { Link, useNavigate } from "react-router-dom";
import PrimaryButton from "../components/PrimaryButton";
import api from "../api/axios";

const passwordRules =
  /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d@$!%*?&#^().,_-]{8,}$/;

// const schema = z
//   .object({
//     email: z.string().email("Zadej platný e-mail"),
//     password: z
//       .string()
//       .regex(passwordRules, "Min. 8 znaků, malé/VELKÉ písmeno a číslo"),
//     confirm: z.string(),
//     firstName: z.string().min(2, "Min. 2 znaky"),
//     lastName: z.string().min(2, "Min. 2 znaky"),
//     agree: z.literal(true, {
//       errorMap: () => ({ message: "Musíš souhlasit s podmínkami" }),
//     }),
//   })
//   .refine((data) => data.password === data.confirm, {
//     message: "Hesla se neshodují",
//     path: ["confirm"],
//   });

const submit = async (e) => {
  debugger;

  e.preventDefault();
  try {
    await api.post("/auth/register", { email, password });
    nav("/login");
  } catch (err) {
    console.error(err);
    alert("Register failed");
  }
};

function RegisterPage() {
  const navigate = useNavigate();
  return (
    <div className="register">
      <h1 className="register__title">Registrace</h1>
      <form onSubmit={submit} className="register__form">
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

        <label className="register__label" htmlFor="password">
          Heslo znovu:
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
