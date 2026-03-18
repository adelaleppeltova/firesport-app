import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const BottomNavbar = () => {
  const { user } = useAuth();

  return (
    <nav className="bottom-navbar">
      <ul className="bottom-navbar-links">
        <li>
          <NavLink to="/home" className="nav-item">
            <i className="fa-solid fa-house"></i>
            <span>Domů</span>
          </NavLink>
        </li>
        <li>
          <NavLink to="/zavodnici" className="nav-item">
            <i className="fa-solid fa-user"></i>
            <span>Závodníci</span>
          </NavLink>
        </li>
        <li>
          <NavLink to="/statistiky" className="nav-item">
            <i className="fa-solid fa-chart-bar"></i>
            <span>Statistiky</span>
          </NavLink>
        </li>
        <li>
          <NavLink to="/zavody" className="nav-item">
            <i className="fa-solid fa-flag-checkered"></i>
            <span>Závody</span>
          </NavLink>
        </li>
        {user?.role === "admin" ? (
          <li>
            <NavLink to="/admin" className="nav-item">
              <i className="fa-solid fa-shield-halved"></i>
              <span>Admin</span>
            </NavLink>
          </li>
        ) : null}
      </ul>
    </nav>
  );
};

export default BottomNavbar;
