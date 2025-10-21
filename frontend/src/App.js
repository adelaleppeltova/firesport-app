import { BrowserRouter, Routes, Route } from "react-router-dom";
import HomePage from "./pages/HomePage";
import ErrorPage from "./pages/ErrorPage";
import AppLayout from "./layouts/AppLayout";
import WelcomePage from "./pages/WelcomePage";

const App = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route path="/zavodnici" element={<div>Závodníci</div>} />
          <Route path="/statistiky" element={<div>Statistiky</div>} />
          <Route path="/tymy" element={<div>Týmy</div>} />
          <Route path="*" element={<ErrorPage />} />
          <Route path="/welcome" element={<WelcomePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
