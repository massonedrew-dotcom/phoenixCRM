import { Navigate, Outlet, RouterProvider, createBrowserRouter, useLocation } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { AdminPage } from "./pages/AdminPage";
import { LoginPage } from "./pages/LoginPage";
import { PropertyPage } from "./pages/PropertyPage";
import { SearchPage } from "./pages/SearchPage";

function RequireAuth() {
  const { state } = useAuth();
  const location = useLocation();
  if (state.status === "loading") {
    return <div className="page-loading">Загрузка…</div>;
  }
  if (state.status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}

function RequireManager() {
  const { state } = useAuth();
  if (state.status === "authenticated" && state.user.role === "agent") {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

const FUTURE_FLAGS = {
  v7_relativeSplatPath: true,
  v7_fetcherPersist: true,
  v7_normalizeFormMethod: true,
  v7_partialHydration: true,
  v7_skipActionErrorRevalidation: true,
};

const router = createBrowserRouter(
  [
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      { path: "/", element: <SearchPage /> },
      { path: "/properties/new", element: <PropertyPage /> },
      { path: "/properties/:propertyId", element: <PropertyPage /> },
      { element: <RequireManager />, children: [{ path: "/admin", element: <AdminPage /> }] },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
  ],
  // React Router needs the base without a trailing slash ("/phoenixCRM", not "/phoenixCRM/").
  { future: FUTURE_FLAGS, basename: import.meta.env.BASE_URL.replace(/\/$/, "") },
);

export function App() {
  return <RouterProvider router={router} future={{ v7_startTransition: true }} />;
}
