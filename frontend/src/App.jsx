import { Link, Navigate, Route, Routes } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import DashboardPage from './pages/DashboardPage';
import InterviewPage from './pages/InterviewPage';
import ReportPage from './pages/ReportPage';

function HomeRedirect() {
  return <Navigate to="/dashboard" replace />;
}

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/dashboard">
          <span className="brand-symbol">IA</span>
          <span>InterviewAI</span>
        </Link>
        <div className="topbar-links">
          <Link to="/dashboard">Dashboard</Link>
          <Link className="nav-cta" to="/signup">Get started</Link>
        </div>
      </header>

      <Routes>
        <Route path="/" element={<HomeRedirect />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/interview/:sessionId" element={<InterviewPage />} />
        <Route path="/report/:sessionId" element={<ReportPage />} />
      </Routes>
    </div>
  );
}
