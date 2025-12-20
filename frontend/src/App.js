import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AppLayout from "./layouts/AppLayout";
import BasicLayout from "./layouts/BasicLayout";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import WelcomePage from "./pages/WelcomePage";
import AthletesPage from "./pages/AthletesPage";
import AthleteDetailPage from "./pages/AthleteDetailPage";
import CompetitionsPage from "./pages/CompetitionsPage";
import CompetitionDetailPage from "./pages/CompetitionDetailPage";
import ResultsPage from "./pages/ResultsPage";
import StatisticsPage from "./pages/StatisticsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  const RootPage = () => {
    const { isAuthenticated, loading } = useAuth();
    if (loading) return <div>Loading...</div>;
    if (isAuthenticated) return <Navigate to="/home" replace />;
    return <WelcomePage />;
  };

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<BasicLayout />}>
              <Route path="/" element={<RootPage />} />
              <Route path="/welcome" element={<WelcomePage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
            </Route>
            <Route element={<AppLayout />}>
              <Route path="/home" element={<HomePage />} />
              <Route path="/zavodnici" element={<AthletesPage />} />
              <Route path="/zavody" element={<CompetitionsPage />} />
              <Route path="/zavody/:id" element={<CompetitionDetailPage />} />
              <Route
                path="/zavody/:id/vysledky/:categoryId"
                element={<ResultsPage />}
              />
              <Route path="/zavodnici/:id" element={<AthleteDetailPage />} />
              <Route path="/statistiky" element={<StatisticsPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
