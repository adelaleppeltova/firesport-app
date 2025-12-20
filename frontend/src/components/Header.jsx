import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function Header() {
  const navigate = useNavigate();
  const { isAuthenticated, loading, logout } = useAuth();

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
            className="header__title"
            to={isAuthenticated ? "/home" : "/"}
          >
            firesport
          </NavLink>
        </div>
        <div className="header__items">
          {isAuthenticated ? (
            <NavLink className="header__item" onClick={handleLogout}>
              <i className="fa-solid fa-right-from-bracket"></i>
              <span>Odhlásit se</span>
            </NavLink>
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
