import { useSearchParams } from "react-router-dom";

import { useCurrentUser } from "../auth/AuthContext";
import { AuditTab } from "./admin/AuditTab";
import { DeletedTab } from "./admin/DeletedTab";
import { DistrictsTab } from "./admin/DistrictsTab";
import { UsersTab } from "./admin/UsersTab";
import { ViewsTab } from "./admin/ViewsTab";

type AdminTab = "users" | "audit" | "views" | "districts" | "deleted";

const TAB_LABELS: Record<AdminTab, string> = {
  users: "Пользователи",
  audit: "Журнал изменений",
  views: "Просмотры",
  districts: "Районы",
  deleted: "Удалённые карточки",
};

export function AdminPage() {
  const user = useCurrentUser();
  const [url, setUrl] = useSearchParams();
  const tabs: AdminTab[] =
    user.role === "admin"
      ? ["users", "audit", "views", "districts", "deleted"]
      : ["users", "audit", "views", "deleted"];
  const requested = url.get("tab") as AdminTab | null;
  const tab: AdminTab = requested && tabs.includes(requested) ? requested : "users";

  return (
    <div className="admin-page">
      <h1>Администрирование</h1>
      <div className="tabs" role="tablist">
        {tabs.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            className={tab === name ? "tab active" : "tab"}
            onClick={() => setUrl({ tab: name })}
          >
            {TAB_LABELS[name]}
          </button>
        ))}
      </div>
      {tab === "users" && <UsersTab canManage={user.role === "admin"} currentUserId={user.id} />}
      {tab === "audit" && <AuditTab />}
      {tab === "views" && <ViewsTab />}
      {tab === "districts" && <DistrictsTab />}
      {tab === "deleted" && <DeletedTab />}
    </div>
  );
}
