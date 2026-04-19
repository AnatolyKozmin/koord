<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, setRole, setToken } from "../api/client";

const email = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);
const route = useRoute();
const router = useRouter();

async function submit() {
  error.value = "";
  loading.value = true;
  try {
    const res = await api.login(email.value, password.value);
    setToken(res.access_token);
    const me = await api.me();
    setRole(me.role);
    const redirect = (route.query.redirect as string) || "/subs";
    await router.replace(redirect);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Ошибка входа";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="card" style="max-width: 400px; margin: 4rem auto">
    <h1 style="margin-top: 0">Вход</h1>
    <p class="muted">Супер-админ и обычные пользователи (роли на бэкенде).</p>
    <form @submit.prevent="submit">
      <div class="field">
        <label for="email">Email</label>
        <input id="email" v-model="email" type="email" autocomplete="username" required />
      </div>
      <div class="field">
        <label for="password">Пароль</label>
        <input id="password" v-model="password" type="password" autocomplete="current-password" required />
      </div>
      <p v-if="error" style="color: #f88">{{ error }}</p>
      <button type="submit" class="btn btn-primary" :disabled="loading">{{ loading ? "…" : "Войти" }}</button>
    </form>
  </div>
</template>
