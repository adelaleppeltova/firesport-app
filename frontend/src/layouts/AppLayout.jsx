import Header from "../components/Header";
import Footer from "../components/Footer";
import BottomNavbar from "../components/BottomNavbar";
import { Outlet, Navigate } from "react-router-dom";
import SideNavbar from "../components/SideNavbar";
import FlashBanner from "../components/FlashBanner";
import { useAuth } from "../context/AuthContext";

const AppLayout = () => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/welcome" replace />;
  }

  return (
    <div className="app-layout">
      <Header />
      <FlashBanner />
      <div className="app-body">
        {isAuthenticated && <SideNavbar />}
        <main className={`main ${isAuthenticated ? "sidebar" : ""}`}>
          <Outlet />
        </main>
      </div>
      <Footer />
      {isAuthenticated && <BottomNavbar />}
    </div>
  );
};

export default AppLayout;
