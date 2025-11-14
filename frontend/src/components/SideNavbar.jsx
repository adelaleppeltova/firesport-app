import { NavLink } from "react-router-dom";

function SideNavbar() {
  return (
    <aside className="side-menu">
      <ul className="side-menu__links">
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
          <NavLink to="/zavody" className="nav-item">
            <i className="fa-solid fa-flag-checkered"></i>
            <span>Závody</span>
          </NavLink>
        </li>
      </ul>
    </aside>
  );
}

export default SideNavbar;
