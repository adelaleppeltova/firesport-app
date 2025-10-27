import Header from "../components/Header";
import Footer from "../components/Footer";
import BottomNavbar from "../components/BottomNavbar";
import { Outlet } from "react-router-dom";
import SideNavbar from "../components/SideNavbar";

const AppLayout = () => {
  return (
    <div>
      <Header />
      <SideNavbar />
      <main className="main">
        <Outlet />
      </main>
      <BottomNavbar />
    </div>
  );
};

export default AppLayout;
