import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { DEMO } from "../components/DemoBanner";
import { ErrorMessage } from "../components/ErrorMessage";

export function LoginPage() {
  const { state, login } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  if (state.status === "authenticated") {
    const from = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={from} replace />;
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await login(username, password);
    } catch (caught) {
      setError(caught);
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <h1>База объектов</h1>
        <p className="muted">
          {DEMO
            ? "Демонстрационная версия. Логины: admin, head, dilnoza, rustam. Пароль любой."
            : "Войдите, чтобы искать и редактировать карточки"}
        </p>
        <label className="field">
          <span>Логин</span>
          <input
            autoFocus
            autoComplete="username"
            autoCapitalize="none"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>Пароль</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required={!DEMO}
          />
        </label>
        <ErrorMessage error={error} />
        <button type="submit" className="button primary wide" disabled={pending || state.status === "loading"}>
          {pending ? "Вход…" : "Войти"}
        </button>
      </form>
    </div>
  );
}
