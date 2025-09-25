import { NavLink } from "react-router-dom";

const BottomNavbar = () => {
  return (
    <nav className="bottom-navbar">
      <ul className="bottom-navbar-links">
        <li>
          <NavLink to="/" className="nav-item">
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
          <NavLink to="/tymy" className="nav-item">
            <i className="fa-solid fa-people-group"></i>
            <span>Týmy</span>
          </NavLink>
        </li>
      </ul>
    </nav>
  );
};

export default BottomNavbar;
