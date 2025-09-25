import Header from "../components/Header";
import Footer from "../components/Footer";
import BottomNavbar from "../components/BottomNavbar";
import { Outlet } from "react-router-dom";

const AppLayout = () => {
  return (
    <div>
      <Header />
      <main>
        <Outlet />
      </main>
      <BottomNavbar />
    </div>
  );
};

export default AppLayout;
