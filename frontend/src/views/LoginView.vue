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
    const res = await api.login(email.value.trim(), password.value);
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
  <div class="login-wrap">
    <div class="login-card">
      <div class="login-header">
        <img src="/brand/mayak.svg" alt="Маяк" class="login-logo" />
        <h1 class="login-title">Координаторство<span class="login-year">'26</span></h1>
      </div>

      <form @submit.prevent="submit" class="login-form">
        <div class="field">
          <label for="email">Email</label>
          <input id="email" v-model="email" type="email" autocomplete="username" required placeholder="master01@koord.local" />
        </div>
        <div class="field">
          <label for="password">Пароль</label>
          <input id="password" v-model="password" type="password" autocomplete="current-password" required placeholder="••••••••" />
        </div>
        <p v-if="error" class="login-error">{{ error }}</p>
        <button type="submit" class="btn btn-primary login-btn" :disabled="loading">
          {{ loading ? "…" : "Войти" }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 90vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: var(--c-bg-2);
  border: 1px solid var(--c-border-bright);
  border-radius: var(--radius);
  padding: 2.5rem 2rem 2rem;
  position: relative;
  overflow: hidden;
}

.login-card::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(86, 18, 190, 0.1) 0%, transparent 60%);
  pointer-events: none;
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
  position: relative;
}

.login-logo {
  width: auto;
  height: 120px;
  object-fit: contain;
  margin-bottom: 0.75rem;
}

.login-title {
  font-family: var(--font-heading);
  font-size: 2.5rem;
  font-weight: 700;
  margin: 0 0 0.25rem;
  background: var(--grad-accent);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: 0.04em;
}

.login-year {
  opacity: 0.75;
}

.login-subtitle {
  font-size: 0.875rem;
  color: rgba(243, 242, 242, 0.45);
  margin: 0;
  letter-spacing: 0.03em;
}

.login-form {
  position: relative;
}

.login-error {
  color: var(--c-pink);
  font-size: 0.875rem;
  margin: 0 0 0.75rem;
}

.login-btn {
  width: 100%;
  padding: 0.65rem 1rem;
  font-size: 1rem;
  margin-top: 0.25rem;
}
</style>
