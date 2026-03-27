import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AppLayout from "./layouts/AppLayout";
import BasicLayout from "./layouts/BasicLayout";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import WelcomePage from "./pages/WelcomePage";
import AthletesPage from "./pages/AthletesPage";
import AthleteDetailPage from "./pages/AthleteDetailPage";
import CompetitionsPage from "./pages/CompetitionsPage";
import CompetitionDetailPage from "./pages/CompetitionDetailPage";
import ResultsPage from "./pages/ResultsPage";
import StatisticsPage from "./pages/StatisticsPage";
import ErrorPage from "./pages/ErrorPage";
import AdminPage from "./pages/AdminPage";
import ScrollToTop from "./components/ScrollToTop";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  const AdminRoute = ({ children }) => {
    const { user, isAuthenticated, loading } = useAuth();

    if (loading) return <div>Loading...</div>;
    if (!isAuthenticated) return <Navigate to="/vitejte" replace />;
    if (user?.role !== "admin") {
      return <ErrorPage statusCode={403} title="Přístup odepřen" />;
    }
    return children;
  };

  const RootPage = () => {
    const { isAuthenticated, loading } = useAuth();
    if (loading) return <div>Loading...</div>;
    if (isAuthenticated) return <Navigate to="/domu" replace />;
    return <WelcomePage />;
  };

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <ScrollToTop />
          <Routes>
            <Route element={<BasicLayout />}>
              <Route path="/" element={<RootPage />} />
              <Route path="/vitejte" element={<WelcomePage />} />
              <Route path="/prihlaseni" element={<LoginPage />} />
              <Route path="/registrace" element={<RegisterPage />} />
              <Route
                path="/zapomenute-heslo"
                element={<ForgotPasswordPage />}
              />
              <Route path="/obnoveni-hesla" element={<ResetPasswordPage />} />
            </Route>
            <Route element={<AppLayout />}>
              <Route path="/domu" element={<HomePage />} />
              <Route path="/zavodnici" element={<AthletesPage />} />
              <Route path="/zavody" element={<CompetitionsPage />} />
              <Route path="/zavody/:id" element={<CompetitionDetailPage />} />
              <Route
                path="/zavody/:id/vysledky/:categoryId"
                element={<ResultsPage />}
              />
              <Route path="/zavodnici/:id" element={<AthleteDetailPage />} />
              <Route path="/statistiky" element={<StatisticsPage />} />
              <Route
                path="/admin"
                element={
                  <AdminRoute>
                    <AdminPage />
                  </AdminRoute>
                }
              />
            </Route>
            <Route path="*" element={<ErrorPage />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
