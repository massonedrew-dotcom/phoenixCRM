import { ApiError } from "../api/client";

export function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return "Что-то пошло не так. Обновите страницу";
  return "";
}

export function ErrorMessage({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p className="error-text" role="alert">
      {errorText(error)}
    </p>
  );
}
