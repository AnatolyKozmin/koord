<script setup lang="ts">
import { computed, onMounted } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { api, getRole, getToken, setRole, setToken } from "./api/client";

const route = useRoute();
const authed = computed(() => !!getToken());
const isSuperAdmin = computed(() => getRole() === "super_admin");

onMounted(async () => {
  if (!getToken() || getRole()) return;
  try {
    const me = await api.me();
    setRole(me.role);
  } catch {
    /* сессия протухла */
  }
});

function logout() {
  setToken(null);
  setRole(null);
  window.location.href = "/login";
}
</script>

<template>
  <div class="layout">
    <header v-if="authed && route.name !== 'login'" class="top-nav">
      <RouterLink to="/subs" class="nav-logo">
        <img src="/brand/mayak.svg" alt="Маяк" />
        <span class="nav-logo-name">Координаторство'26</span>
      </RouterLink>
      <RouterLink to="/subs">Сабы</RouterLink>
      <RouterLink to="/ankety">Анкеты</RouterLink>
      <RouterLink to="/homework">Домашки</RouterLink>
      <RouterLink to="/interviews">Собеседования</RouterLink>
      <RouterLink to="/dashboard">Дашборд</RouterLink>
      <RouterLink v-if="isSuperAdmin" to="/admin/assign">Назначения</RouterLink>
      <span class="spacer" />
      <button type="button" class="btn" @click="logout">Выйти</button>
    </header>
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>
