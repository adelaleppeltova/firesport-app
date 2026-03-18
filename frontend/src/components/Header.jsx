import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function Header() {
  const navigate = useNavigate();
  const { isAuthenticated, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    navigate("/login", {
      state: {
        flash: { type: "success", message: "Odhlášení proběhlo úspěšně." },
      },
    });
  };

  return (
    <nav className="header">
      <div className="header__content">
        <div className="header__content--center">
          <NavLink
            className="header__brand"
            to={isAuthenticated ? "/home" : "/"}
          >
            <img
              className="header__logo"
              src={`${process.env.PUBLIC_URL}/flamma-logo.svg`}
              alt="Flamma logo"
            />
            <span className="header__title">flamma</span>
          </NavLink>
        </div>
        <div className="header__items">
          {isAuthenticated ? (
            <>
              <button
                type="button"
                className="header__item header__item--button"
                onClick={handleLogout}
                aria-label="Odhlásit se"
              >
                <i
                  className="fa-solid fa-right-from-bracket"
                  aria-hidden="true"
                ></i>
                <span>Odhlásit se</span>
              </button>
            </>
          ) : (
            <NavLink className="header__item" to="/login">
              <i className="fa-solid fa-user"></i>
              <span>Přihlásit se</span>
            </NavLink>
          )}
        </div>
      </div>
    </nav>
  );
}

export default Header;
