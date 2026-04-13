import { motion } from "framer-motion";
import { Link, Route, Routes, NavLink, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import ContentPage from "./pages/ContentPage";
import DashboardPage from "./pages/DashboardPage";
import ReportPage from "./pages/ReportPage";
import TutorPage from "./pages/TutorPage";

const tabs = [
  { to: "/", label: "Tutor", end: true },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/content", label: "Content" },
];

function Nav() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const saved = localStorage.getItem("st_theme");
    const initial = saved === "dark" || saved === "light" ? saved : "light";
    setTheme(initial);
    document.documentElement.setAttribute("data-theme", initial);
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("st_theme", next);
    document.documentElement.setAttribute("data-theme", next);
  };

  return (
    <header className="glass sticky top-0 z-20 border-b border-border">
      <div className="max-w-5xl mx-auto flex items-center justify-between px-5 py-3">
        <Link to="/" className="flex items-center gap-2 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-accent-light flex items-center justify-center text-white text-sm font-bold shadow-sm shadow-accent/30">
            S
          </div>
          <span className="text-lg font-semibold text-text">
            Socratic Tutor
          </span>
        </Link>

        <div className="flex items-center gap-2">
          <nav className="relative flex gap-1 rounded-xl bg-surface-2 p-1 border border-border">
            {tabs.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                end={tab.end}
                className={({ isActive }) =>
                  `relative z-10 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors duration-200 ${
                    isActive ? "text-white" : "text-muted hover:text-text"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <motion.div
                        layoutId="nav-pill"
                        className="absolute inset-0 rounded-lg bg-accent shadow-sm shadow-accent/30"
                        transition={{ type: "spring", stiffness: 400, damping: 30 }}
                      />
                    )}
                    <span className="relative z-10">{tab.label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </nav>
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            title="Toggle dark mode"
            className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-muted hover:text-text"
          >
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </div>
      </div>
    </header>
  );
}

const pageVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
};

export default function App() {
  const location = useLocation();
  useEffect(() => {
    const routeTitles: Record<string, string> = {
      "/": "Tutor",
      "/dashboard": "Dashboard",
      "/content": "Content",
    };
    const title = routeTitles[location.pathname] ?? "Session Report";
    document.title = `${title} · Socratic Tutor`;
  }, [location.pathname]);
  return (
    <div className="min-h-screen flex flex-col">
      <Nav />
      <main className="flex-1 max-w-5xl w-full mx-auto px-5 py-8">
        <motion.div
          key={location.pathname}
          variants={pageVariants}
          initial="initial"
          animate="animate"
          transition={{ duration: 0.25, ease: "easeOut" }}
        >
          <Routes>
            <Route path="/" element={<TutorPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/content" element={<ContentPage />} />
            <Route path="/report/:sessionId" element={<ReportPage />} />
          </Routes>
        </motion.div>
      </main>
    </div>
  );
}
