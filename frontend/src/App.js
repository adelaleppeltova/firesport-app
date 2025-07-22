import { BrowserRouter, Routes, Route } from "react-router-dom";
import HomePage from "./pages/HomePage";
import AthletesPage from "./pages/AthletesPage";
import "./styles/main.scss";

const App = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/athletes" element={<AthletesPage />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
