import { createRouter, createWebHistory } from "vue-router";
import { api, getRole, getToken, setRole } from "../api/client";

const LoginView = () => import("../views/LoginView.vue");
const SubsView = () => import("../views/SubsView.vue");
const AnketyView = () => import("../views/AnketyView.vue");
const HomeworkView = () => import("../views/HomeworkView.vue");
const InterviewsView = () => import("../views/InterviewsView.vue");
const DashboardView = () => import("../views/DashboardView.vue");
const AdminAssignView = () => import("../views/AdminAssignView.vue");

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView, meta: { public: true } },
    { path: "/", redirect: "/subs" },
    { path: "/subs", name: "subs", component: SubsView },
    { path: "/ankety", name: "ankety", component: AnketyView },
    { path: "/polls", redirect: "/ankety" },
    { path: "/homework", name: "homework", component: HomeworkView },
    { path: "/interviews", name: "interviews", component: InterviewsView },
    { path: "/dashboard", name: "dashboard", component: DashboardView },
    {
      path: "/admin/assign",
      name: "admin-assign",
      component: AdminAssignView,
      meta: { requiresSuperAdmin: true },
    },
  ],
});

router.beforeEach(async (to) => {
  if (to.meta.public) return true;
  if (!getToken()) return { path: "/login", query: { redirect: to.fullPath } };
  if (to.meta.requiresSuperAdmin) {
    if (!getRole()) {
      try {
        const me = await api.me();
        setRole(me.role);
      } catch {
        return { path: "/login" };
      }
    }
    if (getRole() !== "super_admin") return { path: "/subs" };
  }
  return true;
});
