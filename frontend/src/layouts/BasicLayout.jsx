import Header from "../components/Header";
import Footer from "../components/Footer";
import { Outlet } from "react-router-dom";
import FlashBanner from "../components/FlashBanner";

export default function BasicLayout() {
  return (
    <div className="basic-layout">
      <Header />
      <FlashBanner />
      <main className="main">
        <Outlet />
      </main>
      {/* <Footer /> */}
    </div>
  );
}
