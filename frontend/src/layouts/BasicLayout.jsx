import Header from "../components/Header";
import Footer from "../components/Footer";
import { Outlet } from "react-router-dom";
import FlashBanner from "../components/FlashBanner"; // přidáno

export default function BasicLayout() {
  return (
    <div>
      <Header />
      <FlashBanner /> {/* přidáno */}
      <main className="main">
        <Outlet />
      </main>
      {/* <Footer /> */}
    </div>
  );
}
