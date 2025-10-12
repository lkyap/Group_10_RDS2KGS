<script setup lang="ts">
import GraphComponent from "./components/GraphComponent.vue"
import "@yfiles/yfiles/view-layout-bridge.js"
</script>

<template>
  <div id="app">
    <header class="app-header">
      <img alt="yFiles logo" src="./assets/yfiles-logo.svg" />
      <div class="app-header__text">
        <h1>yFiles Graph Explorer</h1>
        <p>Select a mapping-generated dataset to inspect relationships interactively.</p>
      </div>
    </header>
    <main class="app-main">
      <graph-component></graph-component>
    </main>
  </div>
</template>

<style scoped>
#app {
  font-family: "Avenir", Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #1f2937;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
}

.app-header {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 1.5rem 2rem 1rem;
  justify-content: center;
}

.app-header img {
  height: 64px;
}

.app-header__text {
  text-align: left;
}

.app-header__text h1 {
  margin: 0 0 0.5rem;
  font-size: 1.8rem;
}

.app-header__text p {
  margin: 0;
  color: #475569;
}

.app-main {
  flex: 1;
  display: flex;
  padding: 0 2rem 2rem;
}

@media (max-width: 768px) {
  .app-header {
    flex-direction: column;
    text-align: center;
  }

  .app-header__text {
    text-align: center;
  }

  .app-main {
    padding: 0 1rem 1.5rem;
  }
}
</style>

