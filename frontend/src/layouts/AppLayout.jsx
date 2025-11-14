import Header from "../components/Header";
import Footer from "../components/Footer";
import BottomNavbar from "../components/BottomNavbar";
import { Outlet } from "react-router-dom";
import SideNavbar from "../components/SideNavbar";
import FlashBanner from "../components/FlashBanner";
import { useAuth } from "../context/AuthContext";

const AppLayout = () => {
  const { isAuthenticated } = useAuth();
  return (
    <div className="app-layout">
      <Header />
      <FlashBanner />
      <div className="app-body">
        {isAuthenticated && <SideNavbar />}
        <main className="main">
          <Outlet />
        </main>
      </div>
      {/* <Footer /> */}
      {isAuthenticated && <BottomNavbar />}
    </div>
  );
};

export default AppLayout;
