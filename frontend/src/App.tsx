import { Routes, Route, NavLink } from "react-router-dom";
import WorkList from "./pages/WorkList";
import WorkDetail from "./pages/WorkDetail";
import AddWork from "./pages/AddWork";
import StreamList from "./pages/StreamList";
import StreamDetail from "./pages/StreamDetail";
import AuthorList from "./pages/AuthorList";
import AuthorDetail from "./pages/AuthorDetail";
import CollectionDetailPage from "./pages/CollectionDetail";
import StatsPage from "./pages/StatsPage";

const nav = [
  { to: "/", label: "Books" },
  { to: "/authors", label: "Authors" },
  { to: "/streams", label: "Streams" },
  { to: "/stats", label: "Stats" },
  { to: "/add", label: "+ Add" },
];

export default function App() {
  return (
    <div className="min-h-screen bg-stone-50 text-stone-900">
      <nav className="bg-stone-900 text-stone-100 px-6 py-3 flex gap-6 items-center">
        <span className="font-semibold tracking-wide mr-4">Bildung</span>
        {nav.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === "/"}
            className={({ isActive }) =>
              isActive
                ? "text-amber-400 font-medium"
                : "text-stone-300 hover:text-white transition-colors"
            }
          >
            {n.label}
          </NavLink>
        ))}
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <Routes>
          <Route path="/" element={<WorkList />} />
          <Route path="/works/:id" element={<WorkDetail />} />
          <Route path="/add" element={<AddWork />} />
          <Route path="/authors" element={<AuthorList />} />
          <Route path="/authors/:id" element={<AuthorDetail />} />
          <Route path="/streams" element={<StreamList />} />
          <Route path="/streams/:id" element={<StreamDetail />} />
          <Route path="/collections/:id" element={<CollectionDetailPage />} />
          <Route path="/stats" element={<StatsPage />} />
        </Routes>
      </main>
    </div>
  );
}
