import { useState } from "react";

export const DEMO = import.meta.env.VITE_DEMO === "1";

/** Tells visitors that this copy keeps its data in their browser, and lets them reset it. */
export function DemoBanner() {
  const [resetting, setResetting] = useState(false);

  if (!DEMO) return null;

  const reset = async () => {
    if (!window.confirm("Вернуть демо-данные в исходный вид? Ваши изменения в этом браузере пропадут.")) {
      return;
    }
    setResetting(true);
    const { resetDemoState } = await import("../demo/store");
    resetDemoState();
    window.location.reload();
  };

  return (
    <div className="demo-banner">
      <span>
        Демонстрационная версия. Данные хранятся только в вашем браузере и не влияют на рабочую базу.
      </span>
      <button type="button" className="link-button" disabled={resetting} onClick={() => void reset()}>
        Сбросить демо-данные
      </button>
    </div>
  );
}
