import { NavLink } from "react-router-dom";

function Header({ isLoggedIn, onLogin, onLogout }) {
  return (
    <nav className="header">
      <div className="header__content">
        {/* <img src="" alt="logo" className="header-logo" /> */}
        <div className="header__content--center">
          <NavLink className="header__title" href="/">
            firesport
          </NavLink>
        </div>
        <div className="header__items">
          {/* <NavLink className="header__item">
            <i class="fa-solid fa-right-from-bracket"></i>
            <span>Odhlásit se</span>
          </NavLink> */}

          <NavLink className="header__item" to="/login">
            <i class="fa-solid fa-user"></i>
            <span>Přihlásit se</span>
          </NavLink>
        </div>
      </div>
    </nav>
  );
}

export default Header;
