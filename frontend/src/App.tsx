import { motion } from "framer-motion";
import { Link, Route, Routes, NavLink, useLocation } from "react-router-dom";
import ContentPage from "./pages/ContentPage";
import DashboardPage from "./pages/DashboardPage";
import TutorPage from "./pages/TutorPage";

const tabs = [
  { to: "/", label: "Tutor", end: true },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/content", label: "Content" },
];

function Nav() {
  return (
    <header className="glass sticky top-0 z-20 border-b border-mist-200/60">
      <div className="max-w-5xl mx-auto flex items-center justify-between px-5 py-3">
        <Link to="/" className="flex items-center gap-2 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-accent-light flex items-center justify-center text-white text-sm font-bold shadow-sm shadow-accent/30">
            S
          </div>
          <span className="text-lg font-semibold gradient-text">
            Socratic Tutor
          </span>
        </Link>

        <nav className="relative flex gap-1 rounded-xl bg-mist-100/80 p-1">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                `relative z-10 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors duration-200 ${
                  isActive ? "text-white" : "text-ink-600 hover:text-ink-800"
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
          </Routes>
        </motion.div>
      </main>
    </div>
  );
}
